import { getAuth } from "@/lib/auth/server";

export const dynamic = "force-dynamic";

// Handlers must be lazy — auth.handler() calls createNeonAuth() which
// requires env vars not available during the Docker build phase.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function GET(...args: any[]) {
  const { GET: handler } = getAuth().handler();
  return handler(...args);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function POST(...args: any[]) {
  const { POST: handler } = getAuth().handler();
  return handler(...args);
}
