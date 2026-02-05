import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import KeywordsPage from '../page';
import type { PageWithKeywords } from '@/lib/api';

// ============================================================================
// Mock Next.js navigation
// ============================================================================
const mockRouterPush = vi.fn();
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'test-project-123' }),
  useRouter: () => ({ push: mockRouterPush }),
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
  isApproved: boolean,
  options?: { volume?: number; score?: number }
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
    search_volume: options?.volume ?? 1000,
    difficulty_score: null,
    is_approved: isApproved,
    is_priority: false,
    alternative_keywords: [
      { keyword: 'alt keyword 1', volume: 500, cpc: 1.5, competition: 0.3, relevance_score: 0.8, composite_score: 45.0 },
      { keyword: 'alt keyword 2', volume: 300, cpc: 1.0, competition: 0.5, relevance_score: 0.7, composite_score: 40.0 },
    ],
    composite_score: options?.score ?? 50.0,
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

interface MockKeywordGeneration {
  status: 'pending' | 'generating' | 'completed' | 'failed';
  completed: number;
  total: number;
  failed: number;
  progress: number;
  currentPage: string | null;
  isLoading: boolean;
  isError: boolean;
  isGenerating: boolean;
  isComplete: boolean;
  isFailed: boolean;
  error: string | null;
  startGeneration: ReturnType<typeof vi.fn>;
  startGenerationAsync: ReturnType<typeof vi.fn>;
  isStarting: boolean;
  startError: Error | null;
  refetch: ReturnType<typeof vi.fn>;
  invalidate: ReturnType<typeof vi.fn>;
  invalidatePagesWithKeywords: ReturnType<typeof vi.fn>;
}

const defaultMockKeywordGen = (overrides?: Partial<MockKeywordGeneration>): MockKeywordGeneration => ({
  status: 'completed' as const,
  completed: 3,
  total: 3,
  failed: 0,
  progress: 100,
  currentPage: null,
  isLoading: false,
  isError: false,
  isGenerating: false,
  isComplete: true,
  isFailed: false,
  error: null,
  startGeneration: vi.fn(),
  startGenerationAsync: vi.fn(),
  isStarting: false,
  startError: null,
  refetch: vi.fn(),
  invalidate: vi.fn(),
  invalidatePagesWithKeywords: vi.fn(),
  ...overrides,
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
// Tests: Page Integration
// ============================================================================
describe('Keywords Page - Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRouterPush.mockClear();
    mockApproveAllMutation.isPending = false;
    mockApproveAllMutation.mutateAsync.mockResolvedValue({ approved_count: 0 });
  });

  // ============================================================================
  // Page loading with mocked API
  // ============================================================================
  describe('page loads with mocked API', () => {
    it('renders loading skeleton while project is loading', () => {
      mockUseProject.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen({ isLoading: true }));
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
      expect(screen.getByText('All Projects')).toBeInTheDocument();
    });

    it('renders loading skeleton while keyword status is loading', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen({ isLoading: true }));
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
    });

    it('renders not found state when project fetch fails', () => {
      mockUseProject.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Not found'),
      });
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      expect(screen.getByText('Project Not Found')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Back to Dashboard' })).toBeInTheDocument();
    });

    it('renders page successfully with all components when data is loaded', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', false),
        createMockPage('page-2', 'keyword two', true),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // Breadcrumb
      expect(screen.getByText('Test Project')).toBeInTheDocument();
      expect(screen.getByText('Onboarding')).toBeInTheDocument();

      // Step indicator
      expect(screen.getByText(/Step 3 of 5/)).toBeInTheDocument();

      // Page title
      expect(screen.getByText('2 Keywords Generated')).toBeInTheDocument();

      // Keywords list
      expect(screen.getByText('keyword one')).toBeInTheDocument();
      expect(screen.getByText('keyword two')).toBeInTheDocument();
    });

    it('renders step indicator with correct step highlighted', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      // Check for step label text
      expect(screen.getByText(/Step 3 of 5: Keywords/)).toBeInTheDocument();

      // Check step labels
      expect(screen.getByText('Upload')).toBeInTheDocument();
      expect(screen.getByText('Crawl')).toBeInTheDocument();
      expect(screen.getByText('Keywords')).toBeInTheDocument();
      expect(screen.getByText('Content')).toBeInTheDocument();
      expect(screen.getByText('Export')).toBeInTheDocument();
    });

    it('renders back navigation links', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      // Back to crawl button
      const backButton = screen.getByRole('link', { name: 'Back' });
      expect(backButton).toHaveAttribute('href', '/projects/test-project-123/onboarding/crawl');
    });
  });

  // ============================================================================
  // Generation progress displays
  // ============================================================================
  describe('generation progress displays', () => {
    it('shows "Ready to generate keywords" when status is pending', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen({
        status: 'pending',
        isComplete: false,
        completed: 0,
        total: 0,
      }));
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      expect(screen.getByText(/Ready to generate keywords/)).toBeInTheDocument();
    });

    it('shows "Generate Keywords" button when status is pending and no keywords exist', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen({
        status: 'pending',
        isComplete: false,
        completed: 0,
        total: 0,
      }));
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      const generateButton = screen.getByRole('button', { name: /Generate Keywords/i });
      expect(generateButton).toBeInTheDocument();
      expect(generateButton).not.toBeDisabled();
    });

    it('calls startGeneration when Generate Keywords button is clicked', async () => {
      const user = userEvent.setup();
      const mockStartGeneration = vi.fn();

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen({
        status: 'pending',
        isComplete: false,
        completed: 0,
        total: 0,
        startGeneration: mockStartGeneration,
      }));
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      await user.click(screen.getByRole('button', { name: /Generate Keywords/i }));

      expect(mockStartGeneration).toHaveBeenCalledTimes(1);
    });

    it('shows "Starting..." when generation is starting', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen({
        status: 'pending',
        isComplete: false,
        isStarting: true,
      }));
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      expect(screen.getByRole('button', { name: /Starting.../i })).toBeDisabled();
    });

    it('shows generating state with progress when status is generating', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen({
        status: 'generating',
        isGenerating: true,
        isComplete: false,
        completed: 5,
        total: 10,
        progress: 50,
        currentPage: 'https://example.com/products/item-5',
      }));
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      // Progress text
      expect(screen.getByText(/Generating keywords.../)).toBeInTheDocument();
      expect(screen.getByText(/5\/10 complete/)).toBeInTheDocument();

      // Current page being processed
      expect(screen.getByText(/Processing:/)).toBeInTheDocument();
      expect(screen.getByText(/\/products\/item-5/)).toBeInTheDocument();
    });

    it('shows progress bar during generation', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen({
        status: 'generating',
        isGenerating: true,
        isComplete: false,
        completed: 5,
        total: 10,
      }));
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      // Progress bar is a div with bg-palm-500 inside bg-cream-200
      const progressContainer = document.querySelector('.bg-cream-200.rounded-full');
      expect(progressContainer).toBeInTheDocument();
      const progressBar = progressContainer?.querySelector('.bg-palm-500');
      expect(progressBar).toBeInTheDocument();
      // Check that style attribute contains width (dynamic value)
      expect(progressBar).toHaveAttribute('style', expect.stringContaining('width:'));
    });

    it('shows completed state with checkmark when status is completed', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen({
        status: 'completed',
        isComplete: true,
        completed: 10,
        total: 10,
      }));
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      expect(screen.getByText(/10\/10 keywords generated/)).toBeInTheDocument();
    });

    it('shows failed state with error message when status is failed', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen({
        status: 'failed',
        isFailed: true,
        isComplete: false,
        completed: 3,
        total: 10,
        error: 'API rate limit exceeded',
      }));
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      expect(screen.getByText(/Generation failed/)).toBeInTheDocument();
      expect(screen.getByText(/API rate limit exceeded/)).toBeInTheDocument();
    });

    it('shows "Generating..." disabled button during generation', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen({
        status: 'generating',
        isGenerating: true,
        isComplete: false,
      }));
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      const generatingButton = screen.getByRole('button', { name: /Generating.../i });
      expect(generatingButton).toBeDisabled();
    });
  });

  // ============================================================================
  // Page list renders after generation
  // ============================================================================
  describe('page list renders after generation', () => {
    it('renders page list with keywords when generation is complete', () => {
      const pages = [
        createMockPage('page-1', 'cannabis storage solutions', false, { volume: 1200, score: 55.5 }),
        createMockPage('page-2', 'hemp products guide', true, { volume: 800, score: 48.2 }),
        createMockPage('page-3', 'cbd oil benefits', true, { volume: 2500, score: 62.0 }),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // Check all keywords are displayed
      expect(screen.getByText('cannabis storage solutions')).toBeInTheDocument();
      expect(screen.getByText('hemp products guide')).toBeInTheDocument();
      expect(screen.getByText('cbd oil benefits')).toBeInTheDocument();
    });

    it('displays search volume for each keyword', () => {
      const pages = [
        createMockPage('page-1', 'test keyword', false, { volume: 1500 }),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // Volume is displayed with "vol" suffix in the badge
      // Use getAllByText and verify at least one exists with the expected content
      const volumeBadges = screen.getAllByText((content, element) =>
        element?.tagName === 'SPAN' &&
        element?.textContent?.includes('1,500') &&
        element?.textContent?.includes('vol')
      );
      expect(volumeBadges.length).toBeGreaterThan(0);
    });

    it('displays composite score for each keyword', () => {
      const pages = [
        createMockPage('page-1', 'test keyword', false, { score: 55.5 }),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // Score is displayed with "score" suffix in the badge
      expect(screen.getByText('55.5 score')).toBeInTheDocument();
    });

    it('shows summary stats with correct counts', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', false),
        createMockPage('page-3', 'keyword three', true),
        createMockPage('page-4', 'keyword four', false),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // Summary stats
      expect(screen.getByText((content, element) =>
        element?.textContent === '4 keywords generated'
      )).toBeInTheDocument();
      expect(screen.getByText((content, element) =>
        element?.textContent === '2 approved'
      )).toBeInTheDocument();
      expect(screen.getByText((content, element) =>
        element?.textContent === '2 pending'
      )).toBeInTheDocument();
    });

    it('shows skeleton loading rows while pages are loading', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue({
        pages: [],
        isLoading: true,
        isError: false,
        error: null,
        refetch: vi.fn(),
        invalidate: vi.fn(),
      });

      render(<KeywordsPage />);

      // Check for skeleton loading rows with animate-pulse class
      const skeletonRows = document.querySelectorAll('.animate-pulse');
      expect(skeletonRows.length).toBeGreaterThan(0);
    });

    it('shows empty state when page list is empty', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      expect(screen.getByText('No Pages Available')).toBeInTheDocument();
      expect(screen.getByText('No crawled pages found. Please complete the crawl step first.')).toBeInTheDocument();
    });

    it('renders pages without keywords (null keywords)', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', false),
        createMockPageWithoutKeywords('page-2'),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // Page with keyword should show
      expect(screen.getByText('keyword one')).toBeInTheDocument();
      // Page without keyword should also render (row exists)
      expect(screen.getByText('Page page-2')).toBeInTheDocument();
    });

    it('shows error state when pages fetch fails', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue({
        pages: [],
        isLoading: false,
        isError: true,
        error: new Error('Network error: Failed to fetch pages'),
        refetch: vi.fn(),
        invalidate: vi.fn(),
      });

      render(<KeywordsPage />);

      expect(screen.getByText('Failed to Load Pages')).toBeInTheDocument();
      expect(screen.getByText('Network error: Failed to fetch pages')).toBeInTheDocument();
    });

    it('shows retry button on error and calls refetch when clicked', async () => {
      const mockRefetch = vi.fn().mockResolvedValue({});

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue({
        pages: [],
        isLoading: false,
        isError: true,
        error: new Error('Failed to fetch'),
        refetch: mockRefetch,
        invalidate: vi.fn(),
      });

      render(<KeywordsPage />);

      const retryButton = screen.getByRole('button', { name: 'Retry' });
      expect(retryButton).toBeInTheDocument();

      await userEvent.click(retryButton);

      expect(mockRefetch).toHaveBeenCalled();
    });

    it('shows retrying state when retry button is clicked', async () => {
      // Create a promise that we can control
      let resolveRefetch: () => void;
      const refetchPromise = new Promise<void>((resolve) => {
        resolveRefetch = resolve;
      });
      const mockRefetch = vi.fn().mockReturnValue(refetchPromise);

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue({
        pages: [],
        isLoading: false,
        isError: true,
        error: new Error('Failed to fetch'),
        refetch: mockRefetch,
        invalidate: vi.fn(),
      });

      render(<KeywordsPage />);

      const retryButton = screen.getByRole('button', { name: 'Retry' });
      await userEvent.click(retryButton);

      // Should show retrying state
      expect(screen.getByText('Retrying...')).toBeInTheDocument();
      expect(retryButton).toBeDisabled();

      // Resolve the refetch promise
      resolveRefetch!();
    });
  });

  // ============================================================================
  // Approve all flow
  // ============================================================================
  describe('approve all flow', () => {
    it('shows Approve All button when pages have keywords', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', false),
        createMockPage('page-2', 'keyword two', false),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      expect(screen.getByRole('button', { name: /Approve All/i })).toBeInTheDocument();
    });

    it('Approve All button is enabled when some keywords are pending', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', false),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      expect(screen.getByRole('button', { name: /Approve All/i })).not.toBeDisabled();
    });

    it('Approve All button is disabled when all keywords are approved', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', true),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      expect(screen.getByRole('button', { name: /Approve All/i })).toBeDisabled();
    });

    it('calls approveAllKeywords mutation when clicked', async () => {
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

      expect(mockApproveAllMutation.mutateAsync).toHaveBeenCalledWith('test-project-123');
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
      expect(screen.getByRole('button', { name: /Approving.../i })).toBeDisabled();
    });

    it('shows success toast after Approve All succeeds', async () => {
      const user = userEvent.setup();
      const pages = [
        createMockPage('page-1', 'keyword one', false),
        createMockPage('page-2', 'keyword two', false),
        createMockPage('page-3', 'keyword three', false),
      ];

      mockApproveAllMutation.mutateAsync.mockResolvedValue({ approved_count: 3 });
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

    it('shows approval progress display with correct counts', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', false),
        createMockPage('page-3', 'keyword three', true),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      // Approval progress display
      expect(screen.getByText(/Approved:/)).toBeInTheDocument();
    });

    it('shows styled badge with checkmark when all approved', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', true),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      const approvalBadge = screen.getByText(/Approved: 2 of 2/);
      expect(approvalBadge).toBeInTheDocument();
      expect(approvalBadge.closest('span')).toHaveClass('bg-palm-50');
    });

    it('enables Continue button when all keywords are approved', () => {
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

    it('navigates to content page when Continue is clicked with all approved', async () => {
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

    it('disables Continue button when some keywords are not approved', () => {
      const pages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', false),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      render(<KeywordsPage />);

      const continueButton = screen.getByRole('button', { name: /Continue to Content/i });
      expect(continueButton).toBeDisabled();
    });
  });

  // ============================================================================
  // Edge cases
  // ============================================================================
  describe('edge cases', () => {
    it('handles project with no data gracefully', () => {
      mockUseProject.mockReturnValue({
        data: null,
        isLoading: false,
        error: null,
      });
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages([]));

      render(<KeywordsPage />);

      expect(screen.getByText('Project Not Found')).toBeInTheDocument();
    });

    it('handles pages loading state with generating status', () => {
      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen({
        status: 'generating',
        isGenerating: true,
        isComplete: false,
      }));
      mockPagesWithKeywords.mockReturnValue({
        pages: [],
        isLoading: true,
        isError: false,
        error: null,
        refetch: vi.fn(),
        invalidate: vi.fn(),
      });

      render(<KeywordsPage />);

      // Check for skeleton loading rows with animate-pulse class
      const skeletonRows = document.querySelectorAll('.animate-pulse');
      expect(skeletonRows.length).toBeGreaterThan(0);
    });

    it('updates UI when rerender with new approved state', async () => {
      const pages = [
        createMockPage('page-1', 'keyword one', false),
        createMockPage('page-2', 'keyword two', false),
      ];

      mockUseProject.mockReturnValue(defaultMockProject());
      mockKeywordGeneration.mockReturnValue(defaultMockKeywordGen());
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(pages));

      const { rerender } = render(<KeywordsPage />);

      // Initially Continue should be disabled
      expect(screen.getByRole('button', { name: /Continue to Content/i })).toBeDisabled();

      // Simulate all keywords being approved
      const updatedPages = [
        createMockPage('page-1', 'keyword one', true),
        createMockPage('page-2', 'keyword two', true),
      ];
      mockPagesWithKeywords.mockReturnValue(defaultMockPages(updatedPages));

      rerender(<KeywordsPage />);

      // Continue button should now be enabled
      expect(screen.getByRole('button', { name: /Continue to Content/i })).not.toBeDisabled();
    });
  });
});
