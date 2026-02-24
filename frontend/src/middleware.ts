import { type NextRequest, NextResponse } from "next/server";
import { getAuth } from "@/lib/auth/server";

export default async function middleware(request: NextRequest) {
  // TEMPORARY: Auth disabled while Neon Auth Google OAuth is being configured.
  // Remove this block and uncomment the auth logic below once ready.
  return NextResponse.next();

  /* --- AUTH LOGIC (disabled) ---
  // Bypass auth entirely for local development
  if (process.env.NEXT_PUBLIC_AUTH_BYPASS === "true") {
    return NextResponse.next();
  }

  const { pathname } = request.nextUrl;

  // Authenticated users on sign-in page → redirect to home
  if (pathname.startsWith("/auth/sign-in")) {
    try {
      const hasSession = (request.headers.get("cookie") || "").includes(
        "__Secure-neon-auth.session_token"
      );
      if (!hasSession) {
        return NextResponse.next();
      }
      const authResponse = await getAuth().middleware({ loginUrl: "/auth/sign-in" })(request);
      if (authResponse.status === 302 || authResponse.status === 307) {
        return NextResponse.next();
      }
      return NextResponse.redirect(new URL("/", request.url));
    } catch {
      return NextResponse.next();
    }
  }

  // All other routes: SDK middleware handles auth check + redirect
  try {
    const protectRoutes = getAuth().middleware({ loginUrl: "/auth/sign-in" });
    return protectRoutes(request);
  } catch {
    return NextResponse.redirect(new URL("/auth/sign-in", request.url));
  }
  --- END AUTH LOGIC --- */
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|fonts|favicon\\.ico|.*\\.png$|.*\\.jpg$|.*\\.svg$|.*\\.ico$|api/auth|api/health).*)"],
};
