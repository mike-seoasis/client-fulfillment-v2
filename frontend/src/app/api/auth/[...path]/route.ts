import { getAuth } from "@/lib/auth/server";
import { type NextRequest } from "next/server";

export const dynamic = "force-dynamic";

// Handlers must be lazy — auth.handler() calls createNeonAuth() which
// requires env vars not available during the Docker build phase.
export function GET(request: NextRequest) {
  const { GET: handler } = getAuth().handler();
  return handler(request);
}

export function POST(request: NextRequest) {
  const { POST: handler } = getAuth().handler();
  return handler(request);
}
