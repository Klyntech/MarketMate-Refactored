import { NextRequest, NextResponse } from "next/server"
import { cookies } from "next/headers"

const BACKEND_URL = process.env.MARKETMATE_API_URL || "http://localhost:8000"

export async function GET(request: NextRequest) {
  try {
    const cookieStore = await cookies()
    const sessionCookie = cookieStore.get("mm_session")

    const response = await fetch(`${BACKEND_URL}/trades`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
      headers: {
        Cookie: sessionCookie ? `mm_session=${sessionCookie.value}` : "",
      },
    })

    // Handle unauthorized — return auth_required flag so frontend shows login prompt
    if (response.status === 401) {
      return NextResponse.json(
        { trades: [], count: 0, auth_required: true },
        { status: 200 }
      )
    }

    // Parse the response body regardless of status
    const data = await response.json().catch(() => ({}))

    // Check for unauthorized in response body (bot returns {"error": "unauthorized"})
    if (data.error === "unauthorized" || data.error === "Unauthorized") {
      return NextResponse.json(
        { trades: [], count: 0, auth_required: true },
        { status: 200 }
      )
    }

    if (!response.ok) {
      return NextResponse.json(
        { trades: [], count: 0, error: data.error || "Failed to fetch trades", backend_down: response.status >= 500 },
        { status: 200 }
      )
    }

    return NextResponse.json(data)
  } catch {
    // Return empty trades with backend_down flag (graceful degradation)
    return NextResponse.json(
      { trades: [], count: 0, error: "Backend unavailable", backend_down: true },
      { status: 200 }
    )
  }
}
