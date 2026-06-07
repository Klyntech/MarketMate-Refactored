import { NextResponse } from "next/server"

export async function GET() {
  const hasNextAuthUrl = !!process.env.NEXTAUTH_URL
  const nextAuthUrl = process.env.NEXTAUTH_URL || "NOT SET"
  const githubId = !!process.env.GITHUB_ID
  const githubSecret = !!process.env.GITHUB_SECRET
  
  // Expected callback URL that NextAuth will construct
  const expectedCallbackUrl = process.env.NEXTAUTH_URL 
    ? `${process.env.NEXTAUTH_URL.replace(/\/$/, "")}/api/auth/callback/github`
    : "CANNOT DETERMINE - NEXTAUTH_URL not set"

  return NextResponse.json({
    providers: {
      github: githubId && githubSecret,
      google: !!(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET),
      email: true,
    },
    debug: {
      NEXTAUTH_URL: nextAuthUrl,
      hasNextAuthUrl,
      GITHUB_ID_set: githubId,
      GITHUB_SECRET_set: githubSecret,
      expected_github_callback_url: expectedCallbackUrl,
      note: "If NEXTAUTH_URL is NOT SET, GitHub OAuth redirect_uri will be wrong. Set it in Render dashboard.",
    }
  })
}
