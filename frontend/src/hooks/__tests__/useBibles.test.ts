/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

import {
  bibleKeys,
  useBibles,
  useBible,
  useCreateBible,
  useUpdateBible,
  useDeleteBible,
  useImportBible,
  useExportBible,
} from '../useBibles';

// =============================================================================
// Mock @/lib/api
// =============================================================================

vi.mock('@/lib/api', () => ({
  getBibles: vi.fn(),
  getBible: vi.fn(),
  createBible: vi.fn(),
  updateBible: vi.fn(),
  deleteBible: vi.fn(),
  importBible: vi.fn(),
  exportBible: vi.fn(),
}));

import {
  getBibles,
  getBible,
  createBible,
  updateBible,
  deleteBible,
  importBible,
  exportBible,
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
  const Wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
  Wrapper.displayName = 'TestQueryWrapper';
  return Wrapper;
}

// =============================================================================
// bibleKeys factory
// =============================================================================

describe('bibleKeys', () => {
  it('list() returns correct key array', () => {
    expect(bibleKeys.list('p1')).toEqual(['projects', 'p1', 'bibles']);
  });

  it('detail() returns correct key array', () => {
    expect(bibleKeys.detail('p1', 'b1')).toEqual([
      'projects',
      'p1',
      'bibles',
      'b1',
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

  it('useBibles is disabled when projectId is empty', () => {
    const { result } = renderHook(() => useBibles(''), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(getBibles).not.toHaveBeenCalled();
  });

  it('useBible is disabled when bibleId is empty', () => {
    const { result } = renderHook(() => useBible('p1', ''), {
      wrapper: createWrapper(),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(getBible).not.toHaveBeenCalled();
  });

  it('useBibles fetches data and unwraps items', async () => {
    const mockItems = [{ id: 'b1', name: 'Bible 1' }];
    vi.mocked(getBibles).mockResolvedValue({
      items: mockItems,
      total: 1,
    } as any);

    const { result } = renderHook(() => useBibles('p1'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(getBibles).toHaveBeenCalledWith('p1');
    // Returns unwrapped items array, not the wrapper
    expect(result.current.data).toEqual(mockItems);
  });
});

// =============================================================================
// Mutation hooks — call correct API functions
// =============================================================================

describe('mutation hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('useCreateBible calls createBible', async () => {
    const mockBible = { id: 'b1', name: 'Test Bible' };
    vi.mocked(createBible).mockResolvedValue(mockBible as any);

    const { result } = renderHook(() => useCreateBible(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      projectId: 'p1',
      data: { name: 'Test Bible' },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(createBible).toHaveBeenCalledWith('p1', { name: 'Test Bible' });
  });

  it('useUpdateBible calls updateBible', async () => {
    const mockBible = { id: 'b1', name: 'Updated Bible' };
    vi.mocked(updateBible).mockResolvedValue(mockBible as any);

    const { result } = renderHook(() => useUpdateBible(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      projectId: 'p1',
      bibleId: 'b1',
      data: { name: 'Updated Bible' },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(updateBible).toHaveBeenCalledWith('p1', 'b1', {
      name: 'Updated Bible',
    });
  });

  it('useDeleteBible calls deleteBible', async () => {
    vi.mocked(deleteBible).mockResolvedValue(undefined as any);

    const { result } = renderHook(() => useDeleteBible(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ projectId: 'p1', bibleId: 'b1' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(deleteBible).toHaveBeenCalledWith('p1', 'b1');
  });

  it('useImportBible calls importBible', async () => {
    const mockBible = { id: 'b2', name: 'Imported Bible' };
    vi.mocked(importBible).mockResolvedValue(mockBible as any);

    const { result } = renderHook(() => useImportBible(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      projectId: 'p1',
      markdown: '---\nname: Test\n---\n# Content',
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(importBible).toHaveBeenCalledWith(
      'p1',
      '---\nname: Test\n---\n# Content',
      undefined
    );
  });

  it('useExportBible calls exportBible', async () => {
    const mockExport = { markdown: '# Bible', filename: 'test.md' };
    vi.mocked(exportBible).mockResolvedValue(mockExport as any);

    const { result } = renderHook(() => useExportBible(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({ projectId: 'p1', bibleId: 'b1' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(exportBible).toHaveBeenCalledWith('p1', 'b1');
  });
});
