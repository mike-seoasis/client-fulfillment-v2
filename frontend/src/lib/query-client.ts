import { QueryClient } from "@tanstack/react-query";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000, // 1 minute
        refetchOnWindowFocus: true,
        retry: (failureCount, error) => {
          // Don't retry auth errors — need token refresh, not retries
          if (error instanceof Error && 'status' in error && (error as any).status === 401) {
            return false;
          }
          // Allow up to 3 retries (4 total attempts)
          return failureCount < 3;
        },
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined = undefined;

export function getQueryClient() {
  if (typeof window === "undefined") {
    // Server: always create a new query client
    return makeQueryClient();
  } else {
    // Browser: reuse the same query client
    if (!browserQueryClient) {
      browserQueryClient = makeQueryClient();
    }
    return browserQueryClient;
  }
}
