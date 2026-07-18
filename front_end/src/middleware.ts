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
 * When cookie-based auth is added, extend this to check the access_token
 * cookie and redirect unauthenticated users from protected routes.
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Routes that don't require authentication
const PUBLIC_ROUTES = ["/login", "/register", "/", "/about", "/health"];

// Security headers for most responses (JSON, etc.).
// `X-Frame-Options: DENY` is intentionally NOT included here so that
// sandboxed iframes (e.g. PlotlyHtmlRenderer) can load proxied HTML
// files via Vercel rewrites. The decision is made per-response below.
const BASE_SECURITY_HEADERS: Record<string, string> = {
  "X-Content-Type-Options": "nosniff",
  "X-XSS-Protection": "1; mode=block",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
};

/**
 * Returns the set of security headers that should be attached to a given
 * response. HTML responses (e.g. proxied Plotly HTML, OpenAPI docs) skip
 * the X-Frame-Options header so that sandboxed iframes on the same
 * origin can embed them.
 */
function headersForResponse(
  request: NextRequest,
  response: NextResponse
): Record<string, string> {
  const accept = request.headers.get("accept") || "";
  const isHtmlRequest = accept.includes("text/html");

  // We can't easily inspect the response headers from here, so decide
  // based on the request Accept header. This is a heuristic, but it's
  // good enough: browsers always send `text/html` for top-level page
  // loads and for iframe navigations, while API clients (axios, SWR)
  // send `application/json` (or `*/*`).
  if (isHtmlRequest) {
    // For HTML responses, use SAMEORIGIN so the app can embed HTML
    // served via Vercel rewrites inside its own iframes.
    return { ...BASE_SECURITY_HEADERS, "X-Frame-Options": "SAMEORIGIN" };
  }

  // For API/JSON responses, keep DENY to mitigate clickjacking.
  return { ...BASE_SECURITY_HEADERS, "X-Frame-Options": "DENY" };
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Add security headers to all responses (varies by request type).
  const response = NextResponse.next();
  const headers = headersForResponse(request, response);
  for (const [key, value] of Object.entries(headers)) {
    response.headers.set(key, value);
  }

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
  // Run middleware on all routes except static assets and API
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|api/).*)",
  ],
};
