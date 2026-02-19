"use client";

import { useEffect } from "react";
import { authClient } from "@/lib/auth/client";
import { setSessionToken } from "@/lib/auth-token";

export function AuthTokenSync() {
  const { data } = authClient.useSession();

  useEffect(() => {
    setSessionToken(data?.session?.token ?? null);
  }, [data]);

  return null;
}
