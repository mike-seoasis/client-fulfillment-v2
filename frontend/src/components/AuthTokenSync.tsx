"use client";

import { useEffect } from "react";
import { authClient } from "@/lib/auth/client";
import { setSessionToken } from "@/lib/auth-token";

export function AuthTokenSync({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data, isPending } = authClient.useSession();
  const token = data?.session?.token ?? null;

  // Set token synchronously so it's available before children render
  setSessionToken(token);

  // Also sync via useEffect for session changes
  useEffect(() => {
    setSessionToken(token);
  }, [token]);

  // Block children until session check completes — prevents queries
  // from firing before the auth token is available
  if (isPending) {
    return null;
  }

  return <>{children}</>;
}
