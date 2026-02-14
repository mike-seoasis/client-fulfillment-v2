import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

import {
  blogKeys,
  useBlogCampaigns,
  useBlogCampaign,
  useBlogPostContent,
  useCreateBlogCampaign,
  useUpdateBlogPost,
  useDeleteBlogCampaign,
  useBlogContentStatus,
} from '../useBlogs';

// =============================================================================
// Mock @/lib/api
// =============================================================================

vi.mock('@/lib/api', () => ({
  getBlogCampaigns: vi.fn(),
  getBlogCampaign: vi.fn(),
  getBlogPostContent: vi.fn(),
  createBlogCampaign: vi.fn(),
  updateBlogPost: vi.fn(),
  deleteBlogCampaign: vi.fn(),
  getBlogContentStatus: vi.fn(),
  bulkApproveBlogPosts: vi.fn(),
  triggerBlogContentGeneration: vi.fn(),
  updateBlogPostContent: vi.fn(),
  approveBlogPostContent: vi.fn(),
  recheckBlogPostContent: vi.fn(),
  bulkApproveBlogContent: vi.fn(),
  triggerBlogLinkPlanning: vi.fn(),
  getBlogLinkStatus: vi.fn(),
  getBlogLinkMap: vi.fn(),
  getBlogExport: vi.fn(),
  downloadBlogPostHtml: vi.fn(),
}));

import {
  getBlogCampaigns,
  getBlogCampaign,
  getBlogPostContent,
  createBlogCampaign,
  updateBlogPost,
  deleteBlogCampaign,
  getBlogContentStatus,
} from '@/lib/api';

// =============================================================================
// Test wrapper with QueryClientProvider
// =============================================================================

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

// =============================================================================
// blogKeys factory
// =============================================================================

describe('blogKeys', () => {
  it('list() returns correct key array', () => {
    expect(blogKeys.list('p1')).toEqual(['projects', 'p1', 'blogs']);
  });

  it('detail() returns correct key array', () => {
    expect(blogKeys.detail('p1', 'b1')).toEqual([
      'projects',
      'p1',
      'blogs',
      'b1',
    ]);
  });

  it('contentStatus() returns correct key array', () => {
    expect(blogKeys.contentStatus('p1', 'b1')).toEqual([
      'projects',
      'p1',
      'blogs',
      'b1',
      'content-status',
    ]);
  });

  it('postContent() returns correct key array', () => {
    expect(blogKeys.postContent('p1', 'b1', 'post1')).toEqual([
      'projects',
      'p1',
      'blogs',
      'b1',
      'posts',
      'post1',
      'content',
    ]);
  });

  it('linkStatus() returns correct key array', () => {
    expect(blogKeys.linkStatus('p1', 'b1', 'post1')).toEqual([
      'projects',
      'p1',
      'blogs',
      'b1',
      'posts',
      'post1',
      'link-status',
    ]);
  });

  it('linkMap() returns correct key array', () => {
    expect(blogKeys.linkMap('p1', 'b1', 'post1')).toEqual([
      'projects',
      'p1',
      'blogs',
      'b1',
      'posts',
      'post1',
      'link-map',
    ]);
  });

  it('export() returns correct key array', () => {
    expect(blogKeys.export('p1', 'b1')).toEqual([
      'projects',
      'p1',
      'blogs',
      'b1',
      'export',
    ]);
  });
});

// =============================================================================
// Query hooks — enabled/disabled behavior
// =============================================================================

describe('query hooks enabled/disabled', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('useBlogCampaigns is disabled when projectId is empty', () => {
    const { result } = renderHook(() => useBlogCampaigns(''), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(getBlogCampaigns).not.toHaveBeenCalled();
  });

  it('useBlogCampaign is disabled when blogId is empty', () => {
    const { result } = renderHook(() => useBlogCampaign('p1', ''), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(getBlogCampaign).not.toHaveBeenCalled();
  });

  it('useBlogPostContent is disabled when postId is empty', () => {
    const { result } = renderHook(
      () => useBlogPostContent('p1', 'b1', ''),
      { wrapper: createWrapper() },
    );

    expect(result.current.fetchStatus).toBe('idle');
    expect(getBlogPostContent).not.toHaveBeenCalled();
  });
});

// =============================================================================
// Mutation hooks — call correct API functions
// =============================================================================

describe('mutation hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('useCreateBlogCampaign calls createBlogCampaign', async () => {
    const mockCampaign = { id: 'blog-1', name: 'Test Campaign' };
    vi.mocked(createBlogCampaign).mockResolvedValue(mockCampaign as any);

    const { result } = renderHook(() => useCreateBlogCampaign(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      projectId: 'p1',
      data: { cluster_id: 'c1' } as any,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(createBlogCampaign).toHaveBeenCalledWith('p1', { cluster_id: 'c1' });
  });

  it('useUpdateBlogPost calls updateBlogPost', async () => {
    const mockPost = { id: 'post-1', keyword: 'test' };
    vi.mocked(updateBlogPost).mockResolvedValue(mockPost as any);

    const { result } = renderHook(() => useUpdateBlogPost(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      projectId: 'p1',
      blogId: 'b1',
      postId: 'post-1',
      data: { keyword: 'updated' } as any,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(updateBlogPost).toHaveBeenCalledWith('p1', 'b1', 'post-1', {
      keyword: 'updated',
    });
  });

  it('useDeleteBlogCampaign calls deleteBlogCampaign', async () => {
    vi.mocked(deleteBlogCampaign).mockResolvedValue(undefined as any);

    const { result } = renderHook(() => useDeleteBlogCampaign(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ projectId: 'p1', blogId: 'b1' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(deleteBlogCampaign).toHaveBeenCalledWith('p1', 'b1');
  });
});

// =============================================================================
// Polling behavior — useBlogContentStatus
// =============================================================================

describe('useBlogContentStatus polling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('polls when overall_status is generating and stops when complete', async () => {
    // Return 'generating' on every call — we just need to verify it keeps fetching
    vi.mocked(getBlogContentStatus).mockResolvedValue({
      overall_status: 'generating',
      posts: [],
    } as any);

    // Use a short refetchInterval-friendly wrapper with a tight query client
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);

    const { result } = renderHook(
      () => useBlogContentStatus('p1', 'b1'),
      { wrapper },
    );

    // Wait for the initial fetch
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(getBlogContentStatus).toHaveBeenCalledTimes(1);

    // The refetchInterval is 3s — wait a bit more and verify it fetched again
    await waitFor(
      () => expect(getBlogContentStatus).toHaveBeenCalledTimes(2),
      { timeout: 5000 },
    );

    // Now switch to 'complete' — polling should stop
    vi.mocked(getBlogContentStatus).mockResolvedValue({
      overall_status: 'complete',
      posts: [],
    } as any);

    // Wait for the 'complete' response to arrive
    await waitFor(
      () =>
        expect(result.current.data).toEqual(
          expect.objectContaining({ overall_status: 'complete' }),
        ),
      { timeout: 5000 },
    );

    // Record call count after receiving 'complete'
    const callsAfterComplete = vi.mocked(getBlogContentStatus).mock.calls.length;

    // Wait 4 seconds — no additional fetches should happen
    await new Promise((resolve) => setTimeout(resolve, 4000));
    expect(getBlogContentStatus).toHaveBeenCalledTimes(callsAfterComplete);
  }, 20000);
});
