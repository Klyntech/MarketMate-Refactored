import { NextRequest, NextResponse } from "next/server"
import { getServerSession } from "next-auth"
import { authOptions } from "@/app/api/auth/[...nextauth]/route"
import { revokeApiKey, ensureUser } from "@/lib/api-keys"

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const session = await getServerSession(authOptions)
    if (!session?.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const { id } = await params
    const email = session.user.email
    if (!email) {
      return NextResponse.json({ error: "Email not found in session" }, { status: 400 })
    }

    const user = await ensureUser(email, session.user.name || email.split("@")[0])
    await revokeApiKey(id, user.id)
    return NextResponse.json({ success: true })
  } catch (error) {
    console.error("Revoke API key error:", error)
    if (error instanceof Error && error.message === "API key not found") {
      return NextResponse.json({ error: error.message }, { status: 404 })
    }
    return NextResponse.json({ error: "Failed to revoke API key", details: error instanceof Error ? error.message : "Unknown error" }, { status: 500 })
  }
}
