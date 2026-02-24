"use client";

import { useEffect, useRef } from "react";
import { authClient } from "@/lib/auth/client";
import { getSessionToken, setSessionToken } from "@/lib/auth-token";

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
  // mount and fire queries. Only update if changed to avoid overwriting
  // a fresher token set by the 401 refresh mechanism in api.ts.
  if (sessionId && sessionId !== getSessionToken()) {
    setSessionToken(sessionId);
  }

  useEffect(() => {
    if (sessionId) {
      // Only update if changed to avoid overwriting a fresher token
      // set by the 401 refresh mechanism in api.ts.
      if (sessionId !== getSessionToken()) {
        setSessionToken(sessionId);
      }
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

  // Manual session polling — createAuthClient() from @neondatabase/auth/next
  // silently drops any config (including sessionOptions.refetchInterval), so
  // we poll manually to keep the session alive before the 5-min cookie cache
  // expires. Also refreshes when the user returns to the tab.
  useEffect(() => {
    const refreshSessionToken = async () => {
      try {
        const res = await fetch("/api/auth/get-session?disableCookieCache=true", {
          credentials: "include",
        });
        if (!res.ok) return;
        const data = await res.json();
        const newSessionId = data?.session?.id ?? null;
        if (newSessionId && newSessionId !== getSessionToken()) {
          setSessionToken(newSessionId);
        }
      } catch {
        // Silently ignore refresh failures — the 401 retry in api.ts is the fallback
      }
    };

    const intervalId = setInterval(refreshSessionToken, 4 * 60 * 1000); // every 4 minutes

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        refreshSessionToken();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      clearInterval(intervalId);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  // Block children until session check completes — prevents queries
  // from firing before the auth token is available
  if (isPending && !hasInitialized.current) {
    return null;
  }

  return <>{children}</>;
}
