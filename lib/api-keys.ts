import crypto from "crypto"
import { prisma } from "./prisma"

const KEY_PREFIX_LIVE = "mk_live_"
const KEY_PREFIX_TEST = "mk_test_"

// In-memory fallback for environments where SQLite is not persistent (e.g., Render free tier)
// This ensures API keys still work between restarts within the same deploy
const memoryKeys = new Map<string, { id: string; key: string; name: string; prefix: string; environment: string; userId: string; createdAt: Date; revokedAt: Date | null; lastUsed: Date | null }>()
const memoryUsers = new Map<string, { id: string; email: string; name: string }>()
let memoryInitialized = false

// Check if database is available
async function isDatabaseAvailable(): Promise<boolean> {
  try {
    await prisma.$queryRaw`SELECT 1`
    return true
  } catch {
    return false
  }
}

export function generateApiKey(environment: "live" | "test" = "live"): string {
  const prefix = environment === "live" ? KEY_PREFIX_LIVE : KEY_PREFIX_TEST
  const randomBytes = crypto.randomBytes(24).toString("hex")
  return `${prefix}${randomBytes}`
}

export function getKeyPrefix(key: string): string {
  return key.substring(0, 16)
}

export async function validateApiKey(key: string): Promise<{ valid: boolean; userId?: string; environment?: string }> {
  if (!key) return { valid: false }

  // Try database first
  const dbAvailable = await isDatabaseAvailable()
  if (dbAvailable) {
    try {
      const apiKey = await prisma.apiKey.findUnique({
        where: { key },
        select: { userId: true, environment: true, revokedAt: true },
      })

      if (!apiKey || apiKey.revokedAt) return { valid: false }

      // Update lastUsed timestamp (non-blocking)
      prisma.apiKey.update({ where: { key }, data: { lastUsed: new Date() } }).catch(() => {})

      return { valid: true, userId: apiKey.userId, environment: apiKey.environment }
    } catch {
      // Fall through to memory
    }
  }

  // Memory fallback
  const memKey = memoryKeys.get(key)
  if (!memKey || memKey.revokedAt) return { valid: false }

  memKey.lastUsed = new Date()
  return { valid: true, userId: memKey.userId, environment: memKey.environment }
}

export async function ensureUser(email: string, name: string): Promise<{ id: string; email: string; name: string }> {
  // Try database first
  const dbAvailable = await isDatabaseAvailable()
  if (dbAvailable) {
    try {
      const user = await prisma.user.upsert({
        where: { email },
        update: {},
        create: { email, name: name || email.split("@")[0] },
      })
      return user
    } catch {
      // Fall through to memory
    }
  }

  // Memory fallback
  const existing = memoryUsers.get(email)
  if (existing) return existing

  const user = { id: "mem-" + crypto.randomUUID(), email, name: name || email.split("@")[0] }
  memoryUsers.set(email, user)
  return user
}

export async function createApiKey(userId: string, name: string, environment: "live" | "test" = "live") {
  const key = generateApiKey(environment)
  const prefix = getKeyPrefix(key)

  // Try database first
  const dbAvailable = await isDatabaseAvailable()
  if (dbAvailable) {
    try {
      const apiKey = await prisma.apiKey.create({
        data: {
          key,
          name,
          userId,
          prefix,
          environment,
        },
      })

      return {
        id: apiKey.id,
        name: apiKey.name,
        key,
        prefix: apiKey.prefix,
        environment: apiKey.environment,
        createdAt: apiKey.createdAt,
      }
    } catch (error) {
      console.error("Database create failed, using memory fallback:", error)
      // Fall through to memory
    }
  }

  // Memory fallback
  const memKey = {
    id: "mem-" + crypto.randomUUID(),
    key,
    name,
    prefix,
    environment,
    userId,
    createdAt: new Date(),
    revokedAt: null,
    lastUsed: null,
  }
  memoryKeys.set(key, memKey)

  return {
    id: memKey.id,
    name: memKey.name,
    key,
    prefix: memKey.prefix,
    environment: memKey.environment,
    createdAt: memKey.createdAt,
  }
}

export async function revokeApiKey(id: string, userId: string) {
  // Try database first
  const dbAvailable = await isDatabaseAvailable()
  if (dbAvailable) {
    try {
      const apiKey = await prisma.apiKey.findFirst({
        where: { id, userId, revokedAt: null },
      })

      if (!apiKey) throw new Error("API key not found")

      await prisma.apiKey.update({
        where: { id },
        data: { revokedAt: new Date() },
      })

      return { success: true }
    } catch (error) {
      if (error instanceof Error && error.message === "API key not found") throw error
      // Fall through to memory
    }
  }

  // Memory fallback
  for (const [, memKey] of memoryKeys) {
    if (memKey.id === id && memKey.userId === userId && !memKey.revokedAt) {
      memKey.revokedAt = new Date()
      return { success: true }
    }
  }
  throw new Error("API key not found")
}

export async function listApiKeys(userId: string) {
  // Try database first
  const dbAvailable = await isDatabaseAvailable()
  if (dbAvailable) {
    try {
      return prisma.apiKey.findMany({
        where: { userId },
        select: {
          id: true,
          name: true,
          prefix: true,
          environment: true,
          lastUsed: true,
          createdAt: true,
          revokedAt: true,
        },
        orderBy: { createdAt: "desc" },
      })
    } catch {
      // Fall through to memory
    }
  }

  // Memory fallback
  return Array.from(memoryKeys.values())
    .filter(k => k.userId === userId)
    .map(k => ({
      id: k.id,
      name: k.name,
      prefix: k.prefix,
      environment: k.environment,
      lastUsed: k.lastUsed,
      createdAt: k.createdAt,
      revokedAt: k.revokedAt,
    }))
    .sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime())
}
