import { describe, it, expect, vi, beforeEach } from 'vitest';

// ---------------------------------------------------------------------------
// Auth server configuration (frontend/src/lib/auth/server.ts)
// ---------------------------------------------------------------------------
// NOTE: createAuthClient() from @neondatabase/auth/next silently drops all
// arguments, so there is nothing meaningful to test on the client config.
// Session polling is instead tested in AuthTokenSync.test.tsx.
// ---------------------------------------------------------------------------
describe('getAuth config', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('passes sessionDataTtl of 60 to createNeonAuth', async () => {
    const mockCreateNeonAuth = vi.fn().mockReturnValue({});

    vi.doMock('@neondatabase/auth/next/server', () => ({
      createNeonAuth: mockCreateNeonAuth,
    }));

    // Provide required env vars so the factory doesn't throw
    process.env.NEON_AUTH_BASE_URL = 'https://test.example.com';
    process.env.NEON_AUTH_COOKIE_SECRET = 'test-secret';

    const { getAuth } = await import('../auth/server');
    getAuth(); // triggers lazy initialization

    expect(mockCreateNeonAuth).toHaveBeenCalledOnce();

    const args = mockCreateNeonAuth.mock.calls[0][0];
    expect(args.cookies).toEqual(
      expect.objectContaining({
        sessionDataTtl: 60,
      }),
    );
  });

  it('includes baseUrl and cookie secret from env vars', async () => {
    const mockCreateNeonAuth = vi.fn().mockReturnValue({});

    vi.doMock('@neondatabase/auth/next/server', () => ({
      createNeonAuth: mockCreateNeonAuth,
    }));

    process.env.NEON_AUTH_BASE_URL = 'https://my-auth.example.com';
    process.env.NEON_AUTH_COOKIE_SECRET = 'my-secret';

    const { getAuth } = await import('../auth/server');
    getAuth();

    const args = mockCreateNeonAuth.mock.calls[0][0];
    expect(args.baseUrl).toBe('https://my-auth.example.com');
    expect(args.cookies.secret).toBe('my-secret');
  });
});
