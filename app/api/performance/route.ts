import { NextRequest, NextResponse } from "next/server"
import { cookies } from "next/headers"

const BACKEND_URL = process.env.MARKETMATE_API_URL || "http://localhost:8000"

export async function GET(request: NextRequest) {
  try {
    const cookieStore = await cookies()
    const sessionCookie = cookieStore.get("mm_session")

    const response = await fetch(`${BACKEND_URL}/performance`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
      headers: {
        Cookie: sessionCookie ? `mm_session=${sessionCookie.value}` : "",
      },
    })

    // Handle unauthorized
    if (response.status === 401) {
      return NextResponse.json(
        { "7_day": null, "30_day": null, auth_required: true },
        { status: 200 }
      )
    }

    // Parse the response body
    const data = await response.json().catch(() => ({}))

    // Check for unauthorized in response body
    if (data.error === "unauthorized" || data.error === "Unauthorized") {
      return NextResponse.json(
        { "7_day": null, "30_day": null, auth_required: true },
        { status: 200 }
      )
    }

    if (!response.ok) {
      return NextResponse.json(
        { "7_day": null, "30_day": null, error: data.error || "Failed to fetch performance", backend_down: response.status >= 500 },
        { status: 200 }
      )
    }

    return NextResponse.json(data)
  } catch {
    return NextResponse.json(
      { "7_day": null, "30_day": null, error: "Backend unavailable", backend_down: true },
      { status: 200 }
    )
  }
}
