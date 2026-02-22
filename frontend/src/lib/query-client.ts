import { QueryClient } from "@tanstack/react-query";

/**
 * Redirect to sign-in when a 401 is encountered.
 * Debounced so multiple simultaneous 401s don't each trigger a redirect.
 */
let redirectScheduled = false;
function redirectToSignIn() {
  if (redirectScheduled) return;
  redirectScheduled = true;
  // Small delay to let any in-flight requests settle
  setTimeout(() => {
    if (typeof window !== "undefined") {
      window.location.href = "/auth/sign-in";
    }
  }, 100);
}

function isAuthError(error: unknown): boolean {
  return (
    error instanceof Error &&
    "status" in error &&
    (error as any).status === 401
  );
}

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000, // 1 minute
        refetchOnWindowFocus: true,
        retry: (failureCount, error) => {
          // Don't retry auth errors — redirect to sign-in instead
          if (isAuthError(error)) {
            redirectToSignIn();
            return false;
          }
          // Allow up to 3 retries (4 total attempts)
          return failureCount < 3;
        },
      },
      mutations: {
        retry: false,
        onError: (error) => {
          if (isAuthError(error)) {
            redirectToSignIn();
          }
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
