import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock auth-token before importing api module
vi.mock('../auth-token', () => ({
  getSessionToken: () => null,
}));

// Import after mocks are defined
import { api } from '../api';

describe('api fetch timeout', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('rejects with "Request timed out" after 15 seconds', async () => {
    // Replace global fetch with one that aborts when the signal fires
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      (_url, init) =>
        new Promise<Response>((_resolve, reject) => {
          const signal = (init as RequestInit)?.signal;
          if (signal) {
            signal.addEventListener('abort', () => {
              reject(new DOMException('The operation was aborted.', 'AbortError'));
            });
          }
          // Otherwise never resolve (simulates a hanging request)
        }),
    );

    // Start the request -- it will hang until the abort fires
    const promise = api('/test-endpoint');

    // Catch immediately so Node does not flag an unhandled rejection
    const caught = promise.catch((err: Error) => err);

    // Advance time past the 15-second timeout
    await vi.advanceTimersByTimeAsync(16_000);

    const error = await caught as Error;
    expect(error).toBeInstanceOf(Error);
    expect(error.message).toBe('Request timed out');
  });
});
