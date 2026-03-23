/**
 * Hook for fetching app configuration (content mode, app name).
 * Used to detect SEO test mode and show visual indicators.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

interface AppConfig {
  content_mode: "real" | "lorem";
  app_name: string;
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function fetchAppConfig(): Promise<AppConfig> {
  const res = await fetch(`${API_BASE_URL}/config`);
  if (!res.ok) {
    throw new Error("Failed to fetch app config");
  }
  return res.json();
}

export function useAppConfig(): UseQueryResult<AppConfig> {
  return useQuery({
    queryKey: ["app-config"],
    queryFn: fetchAppConfig,
    staleTime: Infinity, // Config doesn't change during a session
    retry: 1,
  });
}
