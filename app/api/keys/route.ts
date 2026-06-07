import { NextRequest, NextResponse } from "next/server"
import { getServerSession } from "next-auth"
import { authOptions } from "@/app/api/auth/[...nextauth]/route"
import { prisma } from "@/lib/prisma"
import { createApiKey, listApiKeys, ensureUser } from "@/lib/api-keys"

export async function GET() {
  try {
    const session = await getServerSession(authOptions)
    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const email = session.user.email
    if (!email) {
      return NextResponse.json({ error: "Email not found in session" }, { status: 400 })
    }

    const user = await ensureUser(email, session.user.name || email.split("@")[0])
    const keys = await listApiKeys(user.id)
    return NextResponse.json({ keys })
  } catch (error) {
    console.error("List API keys error:", error)
    return NextResponse.json({ error: "Failed to list API keys", details: error instanceof Error ? error.message : "Unknown error" }, { status: 500 })
  }
}

export async function POST(request: NextRequest) {
  try {
    const session = await getServerSession(authOptions)
    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    let body: { name?: string; environment?: string }
    try {
      body = await request.json()
    } catch {
      return NextResponse.json({ error: "Invalid request body" }, { status: 400 })
    }

    const { name, environment = "live" } = body

    if (!name || typeof name !== "string" || name.trim().length === 0) {
      return NextResponse.json({ error: "Name is required" }, { status: 400 })
    }

    if (name.length > 50) {
      return NextResponse.json({ error: "Name must be 50 characters or less" }, { status: 400 })
    }

    if (environment !== "live" && environment !== "test") {
      return NextResponse.json({ error: "Environment must be 'live' or 'test'" }, { status: 400 })
    }

    const email = session.user.email
    if (!email) {
      return NextResponse.json({ error: "Email not found in session" }, { status: 400 })
    }

    const user = await ensureUser(email, session.user.name || email.split("@")[0])

    // Check key limit (max 5 per user)
    const existingKeys = await listApiKeys(user.id)
    const activeCount = existingKeys.filter((k: { revokedAt: string | null }) => !k.revokedAt).length

    if (activeCount >= 5) {
      return NextResponse.json({ error: "Maximum of 5 active API keys allowed" }, { status: 400 })
    }

    const apiKey = await createApiKey(user.id, name.trim(), environment)
    return NextResponse.json({ apiKey }, { status: 201 })
  } catch (error) {
    console.error("Create API key error:", error)
    return NextResponse.json({ error: "Failed to create API key", details: error instanceof Error ? error.message : "Unknown error" }, { status: 500 })
  }
}
