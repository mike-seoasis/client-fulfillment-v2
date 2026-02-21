"use client";

import { useEffect, useRef } from "react";
import { authClient } from "@/lib/auth/client";
import { setSessionToken } from "@/lib/auth-token";

export function AuthTokenSync({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data, isPending } = authClient.useSession();
  // Use session.id (UUID) instead of session.token (JWT).
  // The DB stores opaque tokens, but useSession() returns a JWT as
  // session.token — they're different formats and will never match.
  // session.id is the DB primary key and works for lookup.
  const sessionId = data?.session?.id ?? null;

  // Track whether we've completed the initial session load.
  // Don't clear the token during client-side navigation — useSession()
  // can briefly return { data: null, isPending: false } between route
  // transitions, which would wipe the token and cause 401s on in-flight
  // API calls. Only clear after the initial load if we genuinely have
  // no session (i.e. user signed out or session expired server-side).
  const hasInitialized = useRef(false);

  // Set synchronously during render so it's available before children
  // mount and fire queries.
  if (sessionId) {
    setSessionToken(sessionId);
  }

  useEffect(() => {
    if (sessionId) {
      setSessionToken(sessionId);
      hasInitialized.current = true;
    } else if (!isPending && !hasInitialized.current) {
      // Only clear on the very first load when there's genuinely no session
      // (user isn't logged in). After initialization, keep the existing
      // token — if it's truly expired the backend will return 401 and
      // the middleware will redirect to sign-in.
      setSessionToken(null);
      hasInitialized.current = true;
    }
  }, [sessionId, isPending]);

  // Block children until session check completes — prevents queries
  // from firing before the auth token is available
  if (isPending && !hasInitialized.current) {
    return null;
  }

  return <>{children}</>;
}
