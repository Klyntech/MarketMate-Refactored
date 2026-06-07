import { NextResponse } from "next/server"
import { prisma } from "@/lib/prisma"

export async function GET() {
  try {
    // Test database connectivity
    await prisma.$queryRaw`SELECT 1`
    const userCount = await prisma.user.count()
    const keyCount = await prisma.apiKey.count()

    return NextResponse.json({
      status: "ok",
      database: "connected",
      users: userCount,
      apiKeys: keyCount,
    })
  } catch (error) {
    return NextResponse.json({
      status: "degraded",
      database: "unavailable",
      fallback: "in-memory",
      error: error instanceof Error ? error.message : "Unknown error",
    })
  }
}
