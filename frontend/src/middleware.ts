import { type NextRequest, NextResponse } from "next/server";
import { getAuth } from "@/lib/auth/server";

export default async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Authenticated users on sign-in page → redirect to home
  if (pathname.startsWith("/auth/sign-in")) {
    const hasSession = (request.headers.get("cookie") || "").includes(
      "__Secure-neon-auth.session_token"
    );
    if (hasSession) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }

  // All other routes: SDK middleware handles auth check + redirect
  const protectRoutes = getAuth().middleware({ loginUrl: "/auth/sign-in" });
  return protectRoutes(request);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|fonts|favicon\\.ico|api/auth).*)"],
};
