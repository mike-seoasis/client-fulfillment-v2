import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ============================================================================
// Mocks (must be defined before importing the module under test)
// ============================================================================

const mockGetSessionToken = vi.fn<() => string | null>(() => null);
const mockSetSessionToken = vi.fn();

vi.mock("@/lib/auth-token", () => ({
  getSessionToken: (...args: unknown[]) =>
    mockGetSessionToken(...(args as [])),
  setSessionToken: (...args: unknown[]) =>
    mockSetSessionToken(...(args as [])),
}));

const mockUseSession = vi.fn<
  () => { data: { session: { id: string } } | null; isPending: boolean }
>();

vi.mock("@/lib/auth/client", () => ({
  authClient: {
    useSession: () => mockUseSession(),
  },
}));

import { AuthTokenSync } from "../AuthTokenSync";

// ============================================================================
// Helpers
// ============================================================================

function renderWithChildren() {
  return render(
    <AuthTokenSync>
      <div data-testid="child">Child content</div>
    </AuthTokenSync>
  );
}

// ============================================================================
// Tests
// ============================================================================

describe("AuthTokenSync", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --------------------------------------------------------------------------
  // Test 1: Initial sync — token store is empty, session exists
  // --------------------------------------------------------------------------
  it("calls setSessionToken when session exists and getSessionToken returns null (initial sync)", () => {
    mockUseSession.mockReturnValue({
      data: { session: { id: "abc" } },
      isPending: false,
    });
    mockGetSessionToken.mockReturnValue(null);

    renderWithChildren();

    expect(mockSetSessionToken).toHaveBeenCalledWith("abc");
  });

  // --------------------------------------------------------------------------
  // Test 2: No-op — token already matches session
  // --------------------------------------------------------------------------
  it("does NOT call setSessionToken when token already matches session ID", () => {
    mockUseSession.mockReturnValue({
      data: { session: { id: "abc" } },
      isPending: false,
    });
    mockGetSessionToken.mockReturnValue("abc");

    renderWithChildren();

    // Both the synchronous render-path guard and the useEffect guard check
    // `sessionId !== getSessionToken()`. Since they match ("abc" === "abc"),
    // neither path calls setSessionToken.
    expect(mockSetSessionToken).not.toHaveBeenCalled();
  });

  // --------------------------------------------------------------------------
  // Test 3: Different token — session overwrites stale/different token
  // --------------------------------------------------------------------------
  it("calls setSessionToken when session ID differs from current token", () => {
    mockUseSession.mockReturnValue({
      data: { session: { id: "abc" } },
      isPending: false,
    });
    mockGetSessionToken.mockReturnValue("xyz");

    renderWithChildren();

    // The synchronous render-path should call setSessionToken("abc")
    // because "abc" !== "xyz".
    expect(mockSetSessionToken).toHaveBeenCalledWith("abc");
  });

  // --------------------------------------------------------------------------
  // Test 4: Render blocking — isPending with no prior initialization
  // --------------------------------------------------------------------------
  it("does NOT render children when isPending is true and not yet initialized", () => {
    mockUseSession.mockReturnValue({
      data: null,
      isPending: true,
    });
    mockGetSessionToken.mockReturnValue(null);

    renderWithChildren();

    expect(screen.queryByTestId("child")).not.toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Test 5: Children rendered when session is available
  // --------------------------------------------------------------------------
  it("renders children when session is available", () => {
    mockUseSession.mockReturnValue({
      data: { session: { id: "abc" } },
      isPending: false,
    });
    mockGetSessionToken.mockReturnValue(null);

    renderWithChildren();

    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Manual polling tests
  // --------------------------------------------------------------------------
  describe("manual session polling", () => {
    let fetchSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
      vi.useFakeTimers();
      fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response(JSON.stringify({ session: { id: "new-session" } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });

    afterEach(() => {
      vi.useRealTimers();
      fetchSpy.mockRestore();
    });

    // --------------------------------------------------------------------------
    // Test 6: visibilitychange triggers a session refresh
    // --------------------------------------------------------------------------
    it("fetches session on visibilitychange to visible and updates token if session differs", async () => {
      mockUseSession.mockReturnValue({
        data: { session: { id: "abc" } },
        isPending: false,
      });
      mockGetSessionToken.mockReturnValue("abc");

      renderWithChildren();
      mockSetSessionToken.mockClear();

      // Simulate the tab becoming visible
      Object.defineProperty(document, "visibilityState", {
        value: "visible",
        writable: true,
        configurable: true,
      });

      // After the fetch resolves, getSessionToken still returns "abc" but the
      // fetched session is "new-session" — so setSessionToken should be called.
      await act(async () => {
        document.dispatchEvent(new Event("visibilitychange"));
      });

      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/auth/get-session?disableCookieCache=true",
        expect.objectContaining({ credentials: "include" }),
      );
      expect(mockSetSessionToken).toHaveBeenCalledWith("new-session");
    });

    // --------------------------------------------------------------------------
    // Test 7: interval polls every 4 minutes
    // --------------------------------------------------------------------------
    it("polls for session refresh every 4 minutes via setInterval", async () => {
      mockUseSession.mockReturnValue({
        data: { session: { id: "abc" } },
        isPending: false,
      });
      mockGetSessionToken.mockReturnValue("abc");

      renderWithChildren();
      mockSetSessionToken.mockClear();

      // Advance 4 minutes — should trigger the interval callback
      await act(async () => {
        vi.advanceTimersByTime(4 * 60 * 1000);
      });

      expect(fetchSpy).toHaveBeenCalledWith(
        "/api/auth/get-session?disableCookieCache=true",
        expect.objectContaining({ credentials: "include" }),
      );
      expect(mockSetSessionToken).toHaveBeenCalledWith("new-session");
    });
  });
});
