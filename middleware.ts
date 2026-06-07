import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  // Protected routes require authentication
  // For now, just pass through - auth is handled client-side
  return NextResponse.next()
}

export const config = {
  // Protected routes that require authentication
  matcher: ['/desk/:path*', '/dashboard/:path*'],
}
