import { type NextRequest, NextResponse } from "next/server";
import { getAuth } from "@/lib/auth/server";

export default async function middleware(request: NextRequest) {
  // Bypass auth entirely for local development
  if (process.env.NEXT_PUBLIC_AUTH_BYPASS === "true") {
    return NextResponse.next();
  }

  const { pathname } = request.nextUrl;

  // Authenticated users on sign-in page → redirect to home
  if (pathname.startsWith("/auth/sign-in")) {
    // Validate the session properly, not just cookie presence.
    // If the user has a valid session, redirect them away from sign-in.
    // If their session is expired/invalid, let them through to re-authenticate.
    try {
      const hasSession = (request.headers.get("cookie") || "").includes(
        "__Secure-neon-auth.session_token"
      );
      if (!hasSession) {
        return NextResponse.next();
      }
      // Cookie exists — let Neon Auth middleware validate it.
      // If valid, it returns a normal response (not a redirect to sign-in).
      // If invalid, it will redirect to sign-in, which we intercept.
      const authResponse = await getAuth().middleware({ loginUrl: "/auth/sign-in" })(request);
      if (authResponse.status === 302 || authResponse.status === 307) {
        // Neon Auth wants to redirect to sign-in — session is invalid.
        // Let the user stay on sign-in.
        return NextResponse.next();
      }
      // Session is valid — redirect away from sign-in
      return NextResponse.redirect(new URL("/", request.url));
    } catch {
      // If validation fails for any reason, let user access sign-in
      return NextResponse.next();
    }
  }

  // All other routes: SDK middleware handles auth check + redirect
  const protectRoutes = getAuth().middleware({ loginUrl: "/auth/sign-in" });
  return protectRoutes(request);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|fonts|favicon\\.ico|api/auth).*)"],
};
