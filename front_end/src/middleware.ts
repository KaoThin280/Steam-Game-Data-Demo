/**
 * Next.js Middleware - Route protection.
 *
 * NOTE: Tokens are currently stored in localStorage (client-side only).
 * This middleware checks for a cookie-based auth indicator that can be
 * set when httpOnly cookie auth is implemented (Item #5).
 *
 * For now, this middleware handles:
 *   1. Redirecting authenticated users away from /login and /register
 *   2. Adding security headers to responses
 *
 * The matcher below intentionally EXCLUDES /api/* so that proxied
 * responses from Vercel rewrites keep whatever headers the back-end
 * (or Vercel CDN) sets. In particular, /api/v1/data-files/*.html
 * responses must not carry `X-Frame-Options: DENY` because the
 * PlotlyHtmlRenderer component embeds them inside a sandboxed iframe.
 *
 * When cookie-based auth is added, extend this to check the access_token
 * cookie and redirect unauthenticated users from protected routes.
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Routes that don't require authentication
const PUBLIC_ROUTES = ["/login", "/register", "/", "/about", "/health"];

// Security headers applied to top-level pages.
// `X-Frame-Options` is intentionally NOT included here because the
// middleware matcher below excludes /api/*, so these headers don't
// reach the proxied /api/v1/data-files/*.html responses. The
// PlotlyHtmlRenderer iframe then embeds those HTML files without
// being blocked by `X-Frame-Options: DENY`.
const SECURITY_HEADERS: Record<string, string> = {
  "X-Content-Type-Options": "nosniff",
  "X-XSS-Protection": "1; mode=block",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
};

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Add security headers to all responses
  const response = NextResponse.next();
  Object.entries(SECURITY_HEADERS).forEach(([key, value]) => {
    response.headers.set(key, value);
  });

  // Check if user has auth cookie (for future cookie-based auth)
  const hasAuthCookie = request.cookies.has("sgd_access_token");

  // Redirect authenticated users away from login/register
  if (hasAuthCookie && (pathname === "/login" || pathname === "/register")) {
    const redirectUrl = request.nextUrl.clone();
    redirectUrl.pathname = "/dashboard";
    redirectUrl.search = "";
    return NextResponse.redirect(redirectUrl);
  }

  // When cookie-based auth is implemented, add protected route check here:
  // if (!hasAuthCookie && !PUBLIC_ROUTES.some(r => pathname.startsWith(r))) {
  //   const loginUrl = request.nextUrl.clone();
  //   loginUrl.pathname = "/login";
  //   loginUrl.searchParams.set("redirect", pathname);
  //   return NextResponse.redirect(loginUrl);
  // }

  return response;
}

export const config = {
  // Run middleware on all routes except static assets, API routes, and
  // proxied responses. We EXCLUDE /api/* on purpose so that Vercel
  // rewrite responses (e.g. /api/v1/data-files/*.html) keep their
  // own headers from the back-end / Vercel CDN. This lets the
  // PlotlyHtmlRenderer iframe work without being blocked by
  // X-Frame-Options: DENY.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|api/).*)",
  ],
};
