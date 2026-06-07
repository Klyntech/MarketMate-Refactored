import { NextRequest, NextResponse } from "next/server"
import { validateApiKey } from "@/lib/api-keys"

export async function GET(request: NextRequest) {
  const authHeader = request.headers.get("Authorization")
  const apiKey = authHeader?.replace("Bearer ", "")

  if (!apiKey) {
    return NextResponse.json(
      { valid: false, error: "No API key provided" },
      { status: 401 }
    )
  }

  const result = await validateApiKey(apiKey)

  if (!result.valid) {
    return NextResponse.json(
      { valid: false, error: "Invalid or revoked API key" },
      { status: 401 }
    )
  }

  return NextResponse.json({
    valid: true,
    environment: result.environment,
  })
}
