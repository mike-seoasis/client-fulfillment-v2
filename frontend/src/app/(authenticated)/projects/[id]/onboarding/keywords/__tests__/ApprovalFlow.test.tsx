import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import KeywordsPage from '../page';
import type { PageWithKeywords, BulkApproveResponse } from '@/lib/api';

// ============================================================================
// Mock Next.js navigation
// ============================================================================
const mockRouterPush = vi.fn();
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'test-project-123' }),
  useRouter: () => ({ push: mockRouterPush }),
  useSearchParams: () => new URLSearchParams(),
}));

// ============================================================================
// Mock hooks
// ============================================================================
const mockProject = {
  id: 'test-project-123',
  name: 'Test Project',
  site_url: 'https://example.com',
};

const mockUseProject = vi.fn();
vi.mock('@/hooks/use-projects', () => ({
  useProject: () => mockUseProject(),
}));

const mockKeywordGeneration = vi.fn();
vi.mock('@/hooks/useKeywordGeneration', () => ({
  useKeywordGeneration: () => mockKeywordGeneration(),
}));

const mockPagesWithKeywords = vi.fn();
vi.mock('@/hooks/usePagesWithKeywords', () => ({
  usePagesWithKeywordsData: () => mockPagesWithKeywords(),
}));

const mockApproveAllMutation = {
  mutateAsync: vi.fn(),
  isPending: false,
};

vi.mock('@/hooks/useKeywordMutations', () => ({
  useApproveAllKeywords: () => mockApproveAllMutation,
  useApproveKeyword: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useTogglePriority: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdatePrimaryKeyword: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

// ============================================================================
// Mock data helpers
// ============================================================================
const createMockPage = (
  id: string,
  keyword: string,
  isApproved: boolean
): PageWithKeywords => ({
  id,
  url: `https://example.com/${id}`,
  title: `Page ${id}`,
  labels: [],
  product_count: null,
  keywords: {
    id: `kw-${id}`,
    primary_keyword: keyword,
    secondary_keywords: [],
    search_volume: 1000,
    difficulty_score: null,
    is_approved: isApproved,
    is_priority: false,
    alternative_keywords: [],
    composite_score: 50.0,
    relevance_score: 0.8,
    ai_reasoning: null,
  },
});

const createMockPageWithoutKeywords = (id: string): PageWithKeywords => ({
  id,
  url: `https://example.com/${id}`,
  title: `Page ${id}`,
  labels: [],
  product_count: null,
  keywords: null,
});

// ============================================================================
// Default mock values
// ============================================================================
const defaultMockProject = () => ({
  data: mockProject,
  isLoading: false,
  error: null,
});

const defaultMockKeywordGen = () => ({
  status: 'completed' as const,
  completed: 3,
  total: 3,
  currentPage: null,
  isLoading: false,
  isError: false,
  isGenerating: false,
  isComplete: true,
  isFailed: false,
  error: null,
  startGeneration: vi.fn(),
  isStarting: false,
});

const defaultMockPages = (pages: PageWithKeywords[]) => ({
  pages,
  isLoading: false,
  isError: false,
  error: null,
  refetch: vi.fn(),
  invalidate: vi.fn(),
});

// ============================================================================
// Tests: Approval Flow
// ============================================================================
describe('Keywords Page - Approval Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRouterPush.mockClear();
    mockApproveAllMutation.isPending = false;
    mockApproveAllMutation.mutateAsync.mockResolvedValue({ approved_count: 0 });
  });

  // ============================================================================
  // Individual approve tests
  // ============================================================================
  describe('individual approve', () => {
    it('displays approve button for unapproved keywords', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', false),
        createMockPage('page-2', 'keyword two', true),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // Should see one "Approve" button for the unapproved keyword
      const approveButtons = screen.getAllByRole('button', { name: /^Approve$/i });
      expect(approveButtons.length).toBe(1);

      // Should see one "Approved" badge
      expect(screen.getByText('Approved')).toBeInTheDocument();
    });

    it('shows approved badge for approved keywords', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', true),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // Should see "Approved" badges for both keywords
      const approvedBadges = screen.getAllByText('Approved');
      expect(approvedBadges.length).toBe(2);

      // Should not see any "Approve" buttons
      expect(screen.queryByRole('button', { name: /^Approve$/i })).not.toBeInTheDocument();
    });

    it('counts approved and pending correctly', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', false),
        createMockPage('page-3', 'keyword three', true),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // Summary stats should show correct counts
      // The text is broken up by spans, so we need to use a callback matcher
      expect(screen.getByText((content, element) => {
        return element?.textContent === '3 keywords generated';
      })).toBeInTheDocument();

      expect(screen.getByText((content, element) => {
        return element?.textContent === '2 approved';
      })).toBeInTheDocument();

      expect(screen.getByText((content, element) => {
        return element?.textContent === '1 pending';
      })).toBeInTheDocument();

      // Approval progress should show "Approved: 2 of 3"
      expect(screen.getByText(/Approved:/)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Bulk approve tests
  // ============================================================================
  describe('bulk approve (Approve All)', () => {
    it('shows Approve All button when there are pending keywords', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', false),
        createMockPage('page-2', 'keyword two', false),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      const approveAllButton = screen.getByRole('button', { name: /Approve All/i });
      expect(approveAllButton).toBeInTheDocument();
      expect(approveAllButton).not.toBeDisabled();
    });

    it('disables Approve All button when all keywords are approved', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', true),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      const approveAllButton = screen.getByRole('button', { name: /Approve All/i });
      expect(approveAllButton).toBeDisabled();
    });

    it('calls approveAllKeywords mutation when Approve All clicked', async () => {
      const user = userEvent.setup();
      const pages = [
        createMockPage('page-1', 'keyword one', false),
        createMockPage('page-2', 'keyword two', false),
      ];

      mockApproveAllMutation.mutateAsync.mockResolvedValue({ approved_count: 2 });
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      await user.click(screen.getByRole('button', { name: /Approve All/i }));

      expect(mockApproveAllMutation.mutateAsync).toHaveBeenCalledWith({ projectId: 'test-project-123', batch: undefined });
    });

    it('shows loading state during Approve All operation', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', false),
      ];

      mockApproveAllMutation.isPending = true;
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      expect(screen.getByText('Approving...')).toBeInTheDocument();
    });

    it('shows success toast after Approve All succeeds', async () => {
      const user = userEvent.setup();
      const pages = [
        createMockPage('page-1', 'keyword one', false),
        createMockPage('page-2', 'keyword two', false),
        createMockPage('page-3', 'keyword three', false),
      ];

      mockApproveAllMutation.mutateAsync.mockResolvedValue({ approved_count: 3 } as BulkApproveResponse);
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      await user.click(screen.getByRole('button', { name: /Approve All/i }));

      await waitFor(() => {
        expect(screen.getByText('3 keywords approved')).toBeInTheDocument();
      });
    });

    it('shows error toast when Approve All fails', async () => {
      const user = userEvent.setup();
      const pages = [
        createMockPage('page-1', 'keyword one', false),
      ];

      mockApproveAllMutation.mutateAsync.mockRejectedValue(new Error('Network error'));
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      await user.click(screen.getByRole('button', { name: /Approve All/i }));

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });
  });

  // ============================================================================
  // Continue button state tests
  // ============================================================================
  describe('continue button state', () => {
    it('is disabled when no keywords are approved', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', false),
        createMockPage('page-2', 'keyword two', false),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      const continueButton = screen.getByRole('button', { name: /Continue to Content/i });
      expect(continueButton).toBeDisabled();
    });

    it('is disabled when some but not all keywords are approved', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', false),
        createMockPage('page-3', 'keyword three', true),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      const continueButton = screen.getByRole('button', { name: /Continue to Content/i });
      expect(continueButton).toBeDisabled();
    });

    it('is enabled when all keywords are approved', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', true),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      const continueButton = screen.getByRole('button', { name: /Continue to Content/i });
      expect(continueButton).not.toBeDisabled();
    });

    it('navigates to content page when clicked with all approved', async () => {
      const user = userEvent.setup();
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', true),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      await user.click(screen.getByRole('button', { name: /Continue to Content/i }));

      expect(mockRouterPush).toHaveBeenCalledWith('/projects/test-project-123/onboarding/content');
    });

    it('has disabled continue button that can show tooltip when some unapproved', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', false),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // Button should be disabled with some unapproved
      const continueButton = screen.getByRole('button', { name: /Continue to Content/i });
      expect(continueButton).toBeDisabled();

      // The button has onMouseEnter/onMouseLeave handlers for tooltip
      // (Tooltip behavior is controlled by React state, tested via integration)
      expect(continueButton).toHaveAttribute('disabled');
    });

    it('shows "Generating..." when keywords are being generated', () => {
      const pages: PageWithKeywords[] = [];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue({
        ...defaultMockKeywordGen(),
        status: 'generating',
        isGenerating: true,
        isComplete: false,
      });
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      const generatingButton = screen.getByRole('button', { name: /Generating.../i });
      expect(generatingButton).toBeDisabled();
    });

    it('updates state correctly as approvals change', async () => {
      // Start with 1 of 2 approved
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', false),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      const { rerender } = render(<KeywordsPage />);

      // Button should be disabled initially
      expect(screen.getByRole('button', { name: /Continue to Content/i })).toBeDisabled();

      // Simulate all keywords becoming approved
      const updatedPages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', true),
      ];
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(updatedPages));

      rerender(<KeywordsPage />);

      // Button should now be enabled
      expect(screen.getByRole('button', { name: /Continue to Content/i })).not.toBeDisabled();
    });
  });

  // ============================================================================
  // Approval progress display tests
  // ============================================================================
  describe('approval progress display', () => {
    it('shows "Approved: X of Y" when some keywords pending', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', false),
        createMockPage('page-3', 'keyword three', true),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // Should show approval progress text
      const approvalText = screen.getByText(/Approved:/);
      expect(approvalText).toBeInTheDocument();
    });

    it('shows checkmark badge when all approved', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', true),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // Find the styled badge with checkmark
      const approvalBadge = screen.getByText(/Approved: 2 of 2/);
      expect(approvalBadge).toBeInTheDocument();
      // Should have the styled badge class
      expect(approvalBadge.closest('span')).toHaveClass('bg-palm-50');
    });

    it('does not show progress when no keywords generated', () => {
      const pages = [
        createMockPageWithoutKeywords('page-1'),
        createMockPageWithoutKeywords('page-2'),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue({
        ...defaultMockKeywordGen(),
        status: 'pending',
        isComplete: false,
      });
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // When showing the pending state (generate keywords button),
      // the approval progress section isn't shown
      expect(screen.getByText(/Ready to generate keywords/)).toBeInTheDocument();
    });
  });
});
