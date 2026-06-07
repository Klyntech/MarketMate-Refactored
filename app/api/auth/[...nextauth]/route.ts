import NextAuth, { type NextAuthOptions } from "next-auth"
import GithubProvider from "next-auth/providers/github"
import GoogleProvider from "next-auth/providers/google"
import CredentialsProvider from "next-auth/providers/credentials"

const BACKEND_URL = process.env.MARKETMATE_API_URL || "http://localhost:8000"

// Force the correct site URL for OAuth callback construction
// This ensures the redirect_uri matches what's registered in GitHub/Google
// NEXTAUTH_URL should be "https://marketmate-website.onrender.com"
const NEXTAUTH_URL = process.env.NEXTAUTH_URL

export const authOptions: NextAuthOptions = {
  // Explicitly set the site URL so NextAuth constructs correct callback URLs
  // Without this, NextAuth may use internal Render hostnames
  ...(NEXTAUTH_URL && { site: NEXTAUTH_URL.replace(/\/$/, "") }),
  
  providers: [
    GithubProvider({
      clientId: process.env.GITHUB_ID || "",
      clientSecret: process.env.GITHUB_SECRET || "",
    }),
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    }),
    CredentialsProvider({
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email", placeholder: "you@example.com" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error("Email and password are required")
        }

        try {
          // Try to authenticate against the MarketMate bot API
          const response = await fetch(`${BACKEND_URL}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: credentials.email,
              password: credentials.password,
            }),
            signal: AbortSignal.timeout(5000),
          })

          if (response.ok) {
            const data = await response.json()
            return {
              id: data.user?.id || data.id || "1",
              email: credentials.email,
              name: data.user?.name || data.name || credentials.email.split("@")[0],
              accessToken: data.access_token || data.token,
            }
          }

          // If bot API doesn't have auth yet, allow demo login
          if (credentials.email && credentials.password.length >= 6) {
            return {
              id: "demo-" + Date.now(),
              email: credentials.email,
              name: credentials.email.split("@")[0],
            }
          }

          throw new Error("Invalid email or password")
        } catch (error: unknown) {
          // If backend is unreachable, allow demo login for exploration
          if (error instanceof TypeError && error.message.includes("fetch")) {
            if (credentials.email && credentials.password.length >= 6) {
              return {
                id: "demo-" + Date.now(),
                email: credentials.email,
                name: credentials.email.split("@")[0],
              }
            }
          }
          throw new Error(error instanceof Error ? error.message : "Authentication failed")
        }
      },
    }),
  ],
  pages: {
    signIn: "/login",
    signUp: "/signup",
    error: "/login",
  },
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  callbacks: {
    async jwt({ token, user, account }) {
      if (user) {
        token.id = user.id
        if (account?.access_token) {
          token.accessToken = account.access_token
        }
        if ((user as Record<string, unknown>).accessToken) {
          token.accessToken = (user as Record<string, unknown>).accessToken
        }
      }
      return token
    },
    async session({ session, token }) {
      if (session.user) {
        (session.user as Record<string, unknown>).id = token.id
        ;(session.user as Record<string, unknown>).accessToken = token.accessToken
      }
      return session
    },
  },
  secret: process.env.NEXTAUTH_SECRET || "marketmate-dev-secret-change-in-production",
  debug: process.env.NODE_ENV === "development",
}

const handler = NextAuth(authOptions)
export { handler as GET, handler as POST }
