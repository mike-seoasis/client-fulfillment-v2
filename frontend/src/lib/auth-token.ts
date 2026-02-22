const STORAGE_KEY = "grove_session_id";

let sessionToken: string | null = null;

export function setSessionToken(token: string | null) {
  sessionToken = token;
  try {
    if (token) {
      sessionStorage.setItem(STORAGE_KEY, token);
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // sessionStorage unavailable (SSR, private browsing edge cases)
  }
}

export function getSessionToken(): string | null {
  if (sessionToken) return sessionToken;
  // Recover from sessionStorage if module variable was lost
  // (e.g. during hot-reload or Next.js soft navigation edge cases)
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored) {
      sessionToken = stored;
      return stored;
    }
  } catch {
    // sessionStorage unavailable
  }
  return null;
}
