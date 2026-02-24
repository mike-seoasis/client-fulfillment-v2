import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ---- mocks (must be defined before importing the module under test) --------

const mockGetSessionToken = vi.fn<() => string | null>(() => "old-token");
const mockSetSessionToken = vi.fn();

vi.mock("../auth-token", () => ({
  getSessionToken: (...args: unknown[]) => mockGetSessionToken(...(args as [])),
  setSessionToken: (...args: unknown[]) => mockSetSessionToken(...(args as [])),
}));

import { api, ApiError } from "../api";

// ---- helpers ---------------------------------------------------------------

/** Build a minimal Response object. */
function mockResponse(
  status: number,
  body: unknown = {},
  statusText = "OK"
): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText,
    json: () => Promise.resolve(body),
    headers: new Headers(),
  } as unknown as Response;
}

// ---- tests -----------------------------------------------------------------

describe("api() 401 retry with refreshSession", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, "fetch");
    mockGetSessionToken.mockReturnValue("old-token");
    mockSetSessionToken.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls /api/auth/get-session?disableCookieCache=true on 401", async () => {
    // First call: the API request returns 401.
    // Second call: the refresh endpoint returns a new session.
    // Third call: the retried API request succeeds.
    fetchSpy
      .mockResolvedValueOnce(mockResponse(401, {}, "Unauthorized"))
      .mockResolvedValueOnce(
        mockResponse(200, { session: { id: "new-token" } })
      )
      .mockResolvedValueOnce(mockResponse(200, { data: "ok" }));

    await api("/test");

    // The refresh call must include the disableCookieCache query param.
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/auth/get-session?disableCookieCache=true",
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("retries the original request with the new token after successful refresh", async () => {
    mockGetSessionToken
      .mockReturnValueOnce("old-token") // first api() call
      .mockReturnValueOnce("new-token"); // retry call (after setSessionToken)

    fetchSpy
      .mockResolvedValueOnce(mockResponse(401, {}, "Unauthorized"))
      .mockResolvedValueOnce(
        mockResponse(200, { session: { id: "new-token" } })
      )
      .mockResolvedValueOnce(mockResponse(200, { result: 42 }));

    const result = await api<{ result: number }>("/items");

    // setSessionToken should have been called with the refreshed token.
    expect(mockSetSessionToken).toHaveBeenCalledWith("new-token");

    // The retried request (3rd fetch call) should carry the new token.
    const retryCallArgs = fetchSpy.mock.calls[2];
    const retryInit = retryCallArgs[1] as RequestInit;
    expect((retryInit.headers as Record<string, string>).Authorization).toBe(
      "Bearer new-token"
    );

    expect(result).toEqual({ result: 42 });
  });

  it("propagates the 401 error when refresh fails", async () => {
    fetchSpy
      .mockResolvedValueOnce(mockResponse(401, {}, "Unauthorized"))
      .mockResolvedValueOnce(mockResponse(401, {}, "Unauthorized")); // refresh fails

    const error = await api("/secret").catch((e) => e) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(401);
  });

  it("deduplicates concurrent refresh calls", async () => {
    // Both API calls return 401 concurrently.
    // The refresh endpoint should only be called once.
    let refreshCallCount = 0;

    fetchSpy.mockImplementation((url: string | URL | Request) => {
      const urlStr = typeof url === "string" ? url : (url as Request).url;

      if (urlStr.includes("/api/auth/get-session")) {
        refreshCallCount++;
        return Promise.resolve(
          mockResponse(200, { session: { id: "shared-token" } })
        );
      }

      // For the initial API calls, return 401 on first two, then 200 on retries.
      if (urlStr.includes("/endpoint")) {
        // Return 401 for non-retry calls, 200 for retries.
        // We detect retries by checking if the Authorization header has the new token.
        return Promise.resolve(mockResponse(401, {}, "Unauthorized"));
      }

      // Retry calls (after refresh) — return success.
      return Promise.resolve(mockResponse(200, { ok: true }));
    });

    // We need finer control: first two calls 401, refresh once, then two retries succeed.
    fetchSpy.mockReset();

    let apiCallCount = 0;
    fetchSpy.mockImplementation((url: string | URL | Request) => {
      const urlStr = typeof url === "string" ? url : (url as Request).url;

      if (urlStr.includes("/api/auth/get-session")) {
        refreshCallCount++;
        // Add a small delay so both api() calls attach to the same promise.
        return new Promise((resolve) =>
          setTimeout(
            () =>
              resolve(
                mockResponse(200, { session: { id: "shared-token" } })
              ),
            10
          )
        );
      }

      // API endpoint calls
      apiCallCount++;
      if (apiCallCount <= 2) {
        // First two calls (the originals) return 401
        return Promise.resolve(mockResponse(401, {}, "Unauthorized"));
      }
      // Retries return 200
      return Promise.resolve(mockResponse(200, { data: apiCallCount }));
    });

    refreshCallCount = 0;

    const [r1, r2] = await Promise.all([api("/endpoint-a"), api("/endpoint-b")]);

    // Only one refresh call, even though two 401s occurred concurrently.
    expect(refreshCallCount).toBe(1);

    expect(r1).toBeDefined();
    expect(r2).toBeDefined();
  });
});
