import { NextResponse } from "next/server"

const BACKEND_URL = process.env.MARKETMATE_API_URL || "http://localhost:8000"

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000), // 5s timeout
    })

    if (!response.ok) {
      return NextResponse.json(
        { status: "error", message: "Backend returned non-OK", backend_down: true },
        { status: 200 }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch {
    return NextResponse.json(
      { status: "error", message: "Backend connection failed", backend_down: true },
      { status: 200 }
    )
  }
}
