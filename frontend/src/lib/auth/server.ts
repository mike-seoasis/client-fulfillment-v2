import { createNeonAuth } from "@neondatabase/auth/next/server";

// Lazy initialization — env vars aren't available during Docker build.
// All consumers must call getAuth() at request time, not at module level.
let _auth: ReturnType<typeof createNeonAuth> | null = null;

export function getAuth() {
  if (!_auth) {
    _auth = createNeonAuth({
      baseUrl: process.env.NEON_AUTH_BASE_URL!,
      cookies: {
        secret: process.env.NEON_AUTH_COOKIE_SECRET!,
      },
    });
  }
  return _auth;
}
