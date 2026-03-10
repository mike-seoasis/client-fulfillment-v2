import { describe, it, expect } from 'vitest';
import { makeQueryClient } from '../query-client';

describe('makeQueryClient', () => {
  const client = makeQueryClient();
  const defaults = client.getDefaultOptions();

  // ---------------------------------------------------------------------------
  // Stale time
  // ---------------------------------------------------------------------------
  it('has staleTime of 60 000 ms (1 minute)', () => {
    expect(defaults.queries?.staleTime).toBe(60_000);
  });

  // ---------------------------------------------------------------------------
  // Refetch on window focus
  // ---------------------------------------------------------------------------
  it('enables refetchOnWindowFocus', () => {
    expect(defaults.queries?.refetchOnWindowFocus).toBe(true);
  });

  // ---------------------------------------------------------------------------
  // Retry logic
  // ---------------------------------------------------------------------------
  describe('retry function', () => {
    // The retry option is a function — extract it for direct testing.
    const retryFn = defaults.queries?.retry as (
      failureCount: number,
      error: Error,
    ) => boolean;

    it('returns false for 401 errors (auth errors should not retry)', () => {
      const authError = Object.assign(new Error('Unauthorized'), { status: 401 });
      expect(retryFn(0, authError)).toBe(false);
    });

    it('returns true for 500 errors when failureCount < 3 (up to 3 retries)', () => {
      const serverError = Object.assign(new Error('Internal Server Error'), { status: 500 });
      expect(retryFn(0, serverError)).toBe(true);
      expect(retryFn(1, serverError)).toBe(true);
      expect(retryFn(2, serverError)).toBe(true);
    });

    it('returns false when failureCount >= 3', () => {
      const serverError = Object.assign(new Error('Internal Server Error'), { status: 500 });
      expect(retryFn(3, serverError)).toBe(false);
      expect(retryFn(4, serverError)).toBe(false);
    });
  });
});
