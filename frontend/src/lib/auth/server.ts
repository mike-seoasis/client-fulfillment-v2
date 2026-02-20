import { createNeonAuth } from "@neondatabase/auth/next/server";

// Lazy initialization — env vars aren't available during Docker build
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

// Proxy that lazily delegates to the real auth instance at runtime
export const auth = new Proxy({} as ReturnType<typeof createNeonAuth>, {
  get(_target, prop) {
    return (getAuth() as Record<string | symbol, unknown>)[prop];
  },
});
