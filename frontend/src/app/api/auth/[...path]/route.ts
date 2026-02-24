import { getAuth } from "@/lib/auth/server";
import { type NextRequest } from "next/server";

export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ path: string[] }> };

// Handlers must be lazy — auth.handler() calls createNeonAuth() which
// requires env vars not available during the Docker build phase.
let _handlers: ReturnType<ReturnType<typeof getAuth>["handler"]> | null = null;
function handlers() {
  if (!_handlers) _handlers = getAuth().handler();
  return _handlers;
}

export function GET(req: NextRequest, ctx: RouteContext) {
  return handlers().GET(req, ctx);
}

export function POST(req: NextRequest, ctx: RouteContext) {
  return handlers().POST(req, ctx);
}
