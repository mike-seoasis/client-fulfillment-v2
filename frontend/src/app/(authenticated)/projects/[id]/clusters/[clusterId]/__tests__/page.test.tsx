import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ClusterDetailPage from '../page';
import type { Cluster, ClusterPage } from '@/lib/api';

// ============================================================================
// Mock Next.js navigation
// ============================================================================
const mockRouterPush = vi.fn();
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'test-project-123', clusterId: 'cluster-456' }),
  useRouter: () => ({ push: mockRouterPush }),
}));

// ============================================================================
// Mock hooks
// ============================================================================
const mockUseProject = vi.fn();
vi.mock('@/hooks/use-projects', () => ({
  useProject: () => mockUseProject(),
}));

const mockUseCluster = vi.fn();
const mockUpdatePageMutate = vi.fn();
const mockBulkApproveMutate = vi.fn();
const mockRegenerateClusterMutate = vi.fn();
const mockDeleteClusterMutate = vi.fn();
vi.mock('@/hooks/useClusters', () => ({
  useCluster: () => mockUseCluster(),
  useUpdateClusterPage: () => ({
    mutate: mockUpdatePageMutate,
  }),
  useBulkApproveCluster: () => ({
    mutate: mockBulkApproveMutate,
    isPending: false,
  }),
  useRegenerateCluster: () => ({
    mutate: mockRegenerateClusterMutate,
    isPending: false,
  }),
  useDeleteCluster: () => ({
    mutate: mockDeleteClusterMutate,
    isPending: false,
  }),
}));

// ============================================================================
// Mock data helpers
// ============================================================================
const createMockClusterPage = (
  id: string,
  keyword: string,
  role: string,
  isApproved: boolean,
  options?: {
    search_volume?: number;
    cpc?: number;
    composite_score?: number;
    competition_level?: string;
    expansion_strategy?: string;
    url_slug?: string;
  }
): ClusterPage => ({
  id,
  keyword,
  role,
  url_slug: options?.url_slug ?? keyword.replace(/\s+/g, '-').toLowerCase(),
  expansion_strategy: options?.expansion_strategy ?? 'demographic',
  reasoning: null,
  search_volume: options?.search_volume ?? 1000,
  cpc: options?.cpc ?? 1.5,
  competition: 0.45,
  competition_level: options?.competition_level ?? 'MEDIUM',
  composite_score: options?.composite_score ?? 50.0,
  is_approved: isApproved,
  crawled_page_id: null,
});

const createMockCluster = (
  pages: ClusterPage[],
  overrides?: Partial<Cluster>
): Cluster => ({
  id: 'cluster-456',
  project_id: 'test-project-123',
  seed_keyword: 'trail running shoes',
  name: 'Trail Running Shoes',
  status: 'suggestions_ready',
  generation_metadata: null,
  pages,
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
  ...overrides,
});

// ============================================================================
// Default mock values
// ============================================================================
const mockProject = {
  id: 'test-project-123',
  name: 'Test Project',
  site_url: 'https://example.com',
};

const defaultMockProject = () => ({
  data: mockProject,
  isLoading: false,
  error: null,
});

const defaultPages: ClusterPage[] = [
  createMockClusterPage('page-1', 'trail running shoes', 'parent', true, {
    composite_score: 65.0,
    search_volume: 2400,
  }),
  createMockClusterPage('page-2', 'best trail runners 2026', 'child', false, {
    composite_score: 55.0,
    search_volume: 1800,
    expansion_strategy: 'comparison',
  }),
  createMockClusterPage('page-3', 'waterproof trail shoes', 'child', true, {
    composite_score: 48.0,
    search_volume: 900,
    expansion_strategy: 'attribute',
  }),
];

const defaultMockCluster = (pages = defaultPages, overrides?: Partial<Cluster>) => ({
  data: createMockCluster(pages, overrides),
  isLoading: false,
  error: null,
});

// ============================================================================
// Tests
// ============================================================================
describe('ClusterDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProject.mockReturnValue(defaultMockProject());
    mockUseCluster.mockReturnValue(defaultMockCluster());
  });

  // ============================================================================
  // Suggestion list rendering
  // ============================================================================
  describe('suggestion list rendering', () => {
    it('renders all cluster page suggestions', () => {
      render(<ClusterDetailPage />);

      // "trail running shoes" appears in both the seed keyword label and the editable row
      expect(screen.getAllByText('trail running shoes').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('best trail runners 2026')).toBeInTheDocument();
      expect(screen.getByText('waterproof trail shoes')).toBeInTheDocument();
    });

    it('displays cluster name in header', () => {
      render(<ClusterDetailPage />);

      // Header should show cluster name
      const headings = screen.getAllByText('Trail Running Shoes');
      expect(headings.length).toBeGreaterThan(0);
    });

    it('displays seed keyword label', () => {
      render(<ClusterDetailPage />);

      expect(screen.getByText(/Seed keyword:/)).toBeInTheDocument();
    });

    it('displays summary stats with correct counts', () => {
      render(<ClusterDetailPage />);

      // 3 suggestions total, 2 approved, 1 pending
      expect(screen.getByText('3')).toBeInTheDocument(); // total suggestions
      expect(screen.getByText('2')).toBeInTheDocument(); // approved
      expect(screen.getByText('1')).toBeInTheDocument(); // pending
    });

    it('displays search volume for each page', () => {
      render(<ClusterDetailPage />);

      expect(screen.getByText('2,400')).toBeInTheDocument();
      expect(screen.getByText('1,800')).toBeInTheDocument();
      expect(screen.getByText('900')).toBeInTheDocument();
    });

    it('displays CPC for each page', () => {
      render(<ClusterDetailPage />);

      const cpcElements = screen.getAllByText('$1.50');
      expect(cpcElements.length).toBe(3);
    });

    it('displays composite score for each page', () => {
      render(<ClusterDetailPage />);

      expect(screen.getByText('65.0')).toBeInTheDocument();
      expect(screen.getByText('55.0')).toBeInTheDocument();
      expect(screen.getByText('48.0')).toBeInTheDocument();
    });

    it('displays expansion strategy tags', () => {
      render(<ClusterDetailPage />);

      expect(screen.getByText('demographic')).toBeInTheDocument();
      expect(screen.getByText('comparison')).toBeInTheDocument();
      expect(screen.getByText('attribute')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Parent badge display
  // ============================================================================
  describe('parent badge display', () => {
    it('displays Parent badge for parent role pages', () => {
      render(<ClusterDetailPage />);

      expect(screen.getByText('Parent')).toBeInTheDocument();
    });

    it('displays Child badges for child role pages', () => {
      render(<ClusterDetailPage />);

      const childBadges = screen.getAllByText('Child');
      expect(childBadges).toHaveLength(2);
    });

    it('shows Make Parent button only on child rows', () => {
      render(<ClusterDetailPage />);

      const makeParentButtons = screen.getAllByText('Make Parent');
      expect(makeParentButtons).toHaveLength(2); // only child rows
    });
  });

  // ============================================================================
  // Approval toggle
  // ============================================================================
  describe('approval toggle', () => {
    it('renders approve toggles for each page', () => {
      render(<ClusterDetailPage />);

      // 2 approved pages get "Click to reject", 1 unapproved gets "Click to approve"
      const rejectButtons = screen.getAllByTitle('Click to reject');
      const approveButtons = screen.getAllByTitle('Click to approve');
      expect(rejectButtons).toHaveLength(2);
      expect(approveButtons).toHaveLength(1);
    });

    it('calls updateClusterPage when toggle is clicked', async () => {
      const user = userEvent.setup();
      render(<ClusterDetailPage />);

      // Click the reject toggle on the first page (currently approved)
      const rejectButtons = screen.getAllByTitle('Click to reject');
      await user.click(rejectButtons[0]);

      expect(mockUpdatePageMutate).toHaveBeenCalledWith(
        {
          projectId: 'test-project-123',
          clusterId: 'cluster-456',
          pageId: 'page-1',
          data: { is_approved: false },
        },
        expect.objectContaining({
          onError: expect.any(Function),
        })
      );
    });

    it('calls updateClusterPage to approve when unapproved toggle clicked', async () => {
      const user = userEvent.setup();
      render(<ClusterDetailPage />);

      // Click the approve toggle on the unapproved page
      const approveButton = screen.getByTitle('Click to approve');
      await user.click(approveButton);

      expect(mockUpdatePageMutate).toHaveBeenCalledWith(
        {
          projectId: 'test-project-123',
          clusterId: 'cluster-456',
          pageId: 'page-2',
          data: { is_approved: true },
        },
        expect.objectContaining({
          onError: expect.any(Function),
        })
      );
    });
  });

  // ============================================================================
  // Inline editing
  // ============================================================================
  describe('inline editing', () => {
    it('shows editable keyword fields as buttons', () => {
      render(<ClusterDetailPage />);

      const editableButtons = screen.getAllByTitle('Click to edit');
      // Should have editable keyword + url_slug for each page = 6 total
      expect(editableButtons.length).toBe(6);
    });

    it('opens inline editor when keyword is clicked', async () => {
      const user = userEvent.setup();
      render(<ClusterDetailPage />);

      // Click on the first keyword button
      const keywordButton = screen.getByRole('button', { name: 'trail running shoes' });
      await user.click(keywordButton);

      // Should now show an input with the keyword value
      const input = screen.getByDisplayValue('trail running shoes');
      expect(input).toBeInTheDocument();
      expect(input.tagName).toBe('INPUT');
    });

    it('saves keyword on blur with changed value', async () => {
      const user = userEvent.setup();
      render(<ClusterDetailPage />);

      // Click to edit keyword
      const keywordButton = screen.getByRole('button', { name: 'best trail runners 2026' });
      await user.click(keywordButton);

      const input = screen.getByDisplayValue('best trail runners 2026');
      await user.clear(input);
      await user.type(input, 'best trail shoes 2026');
      await user.tab(); // blur

      expect(mockUpdatePageMutate).toHaveBeenCalledWith(
        {
          projectId: 'test-project-123',
          clusterId: 'cluster-456',
          pageId: 'page-2',
          data: { keyword: 'best trail shoes 2026' },
        },
        expect.objectContaining({
          onError: expect.any(Function),
        })
      );
    });
  });

  // ============================================================================
  // Approve All
  // ============================================================================
  describe('Approve All', () => {
    it('renders Approve All button', () => {
      render(<ClusterDetailPage />);

      expect(screen.getByRole('button', { name: /Approve All/i })).toBeInTheDocument();
    });

    it('calls updateClusterPage for each unapproved page when clicked', async () => {
      const user = userEvent.setup();
      render(<ClusterDetailPage />);

      await user.click(screen.getByRole('button', { name: /Approve All/i }));

      // Only page-2 is unapproved
      expect(mockUpdatePageMutate).toHaveBeenCalledWith({
        projectId: 'test-project-123',
        clusterId: 'cluster-456',
        pageId: 'page-2',
        data: { is_approved: true },
      });
    });

    it('disables Approve All when all pages are approved', () => {
      const allApproved = defaultPages.map((p) => ({ ...p, is_approved: true }));
      mockUseCluster.mockReturnValue(defaultMockCluster(allApproved));

      render(<ClusterDetailPage />);

      expect(screen.getByRole('button', { name: /Approve All/i })).toBeDisabled();
    });
  });

  // ============================================================================
  // Generate Content button
  // ============================================================================
  describe('Generate Content button', () => {
    it('renders Generate Content button', () => {
      render(<ClusterDetailPage />);

      expect(screen.getByRole('button', { name: /Generate Content/i })).toBeInTheDocument();
    });

    it('is disabled when no pages are approved', () => {
      const noneApproved = defaultPages.map((p) => ({ ...p, is_approved: false }));
      mockUseCluster.mockReturnValue(defaultMockCluster(noneApproved));

      render(<ClusterDetailPage />);

      expect(screen.getByRole('button', { name: /Generate Content/i })).toBeDisabled();
    });

    it('is enabled when at least one page is approved', () => {
      render(<ClusterDetailPage />);

      expect(screen.getByRole('button', { name: /Generate Content/i })).not.toBeDisabled();
    });

    it('calls bulkApproveCluster when clicked', async () => {
      const user = userEvent.setup();
      render(<ClusterDetailPage />);

      await user.click(screen.getByRole('button', { name: /Generate Content/i }));

      expect(mockBulkApproveMutate).toHaveBeenCalledWith(
        { projectId: 'test-project-123', clusterId: 'cluster-456' },
        expect.objectContaining({
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        })
      );
    });

    it('Generate Content button is disabled with correct label when no pages approved', () => {
      const noneApproved = defaultPages.map((p) => ({ ...p, is_approved: false }));
      mockUseCluster.mockReturnValue(defaultMockCluster(noneApproved));

      render(<ClusterDetailPage />);

      const button = screen.getByRole('button', { name: /Generate Content/i });
      expect(button).toBeDisabled();
      expect(button).toHaveTextContent('Generate Content');
    });
  });

  // ============================================================================
  // Step indicator
  // ============================================================================
  describe('step indicator', () => {
    it('shows Keywords as the current step', () => {
      render(<ClusterDetailPage />);

      expect(screen.getByText(/Step 1 of 4: Keywords/)).toBeInTheDocument();
    });

    it('shows all step labels', () => {
      render(<ClusterDetailPage />);

      expect(screen.getByText('Keywords')).toBeInTheDocument();
      expect(screen.getByText('Content')).toBeInTheDocument();
      expect(screen.getByText('Review')).toBeInTheDocument();
      expect(screen.getByText('Export')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Volume unavailable warning
  // ============================================================================
  describe('volume unavailable warning', () => {
    it('shows warning when volume_unavailable is true', () => {
      mockUseCluster.mockReturnValue(
        defaultMockCluster(defaultPages, {
          generation_metadata: { volume_unavailable: true },
        })
      );

      render(<ClusterDetailPage />);

      expect(
        screen.getByText(/Search volume data was unavailable/)
      ).toBeInTheDocument();
    });

    it('does not show warning when volume data is available', () => {
      render(<ClusterDetailPage />);

      expect(
        screen.queryByText(/Search volume data was unavailable/)
      ).not.toBeInTheDocument();
    });
  });

  // ============================================================================
  // Loading state
  // ============================================================================
  describe('loading state', () => {
    it('shows loading skeleton while data is loading', () => {
      mockUseProject.mockReturnValue({ data: undefined, isLoading: true, error: null });
      mockUseCluster.mockReturnValue({ data: undefined, isLoading: true, error: null });

      render(<ClusterDetailPage />);

      expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Not found states
  // ============================================================================
  describe('not found states', () => {
    it('shows Not Found when project fetch fails', () => {
      mockUseProject.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Not found'),
      });
      mockUseCluster.mockReturnValue({ data: undefined, isLoading: false, error: null });

      render(<ClusterDetailPage />);

      expect(screen.getByText('Not Found')).toBeInTheDocument();
    });

    it('shows Not Found when cluster fetch fails', () => {
      mockUseCluster.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Not found'),
      });

      render(<ClusterDetailPage />);

      expect(screen.getByText('Not Found')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Back navigation
  // ============================================================================
  describe('back navigation', () => {
    it('renders Back to Project button', () => {
      render(<ClusterDetailPage />);

      expect(screen.getByRole('button', { name: /Back to Project/i })).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Regenerate keywords
  // ============================================================================
  describe('regenerate keywords', () => {
    it('renders Regenerate Keywords button for suggestions_ready status', () => {
      render(<ClusterDetailPage />);

      expect(screen.getByRole('button', { name: /Regenerate Keywords/i })).toBeInTheDocument();
    });

    it('does not render Regenerate Keywords button for approved status', () => {
      mockUseCluster.mockReturnValue(
        defaultMockCluster(defaultPages, { status: 'approved' })
      );

      render(<ClusterDetailPage />);

      expect(screen.queryByRole('button', { name: /Regenerate Keywords/i })).not.toBeInTheDocument();
    });

    it('calls regenerateCluster when clicked', async () => {
      const user = userEvent.setup();
      render(<ClusterDetailPage />);

      await user.click(screen.getByRole('button', { name: /Regenerate Keywords/i }));

      expect(mockRegenerateClusterMutate).toHaveBeenCalledWith(
        { projectId: 'test-project-123', clusterId: 'cluster-456' },
        expect.objectContaining({
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        })
      );
    });

    it('is disabled when all pages are approved', () => {
      const allApproved = defaultPages.map((p) => ({ ...p, is_approved: true }));
      mockUseCluster.mockReturnValue(defaultMockCluster(allApproved));

      render(<ClusterDetailPage />);

      expect(screen.getByRole('button', { name: /Regenerate Keywords/i })).toBeDisabled();
    });
  });

  // ============================================================================
  // Delete cluster
  // ============================================================================
  describe('delete cluster', () => {
    it('renders Delete Cluster button for suggestions_ready status', () => {
      render(<ClusterDetailPage />);

      expect(screen.getByRole('button', { name: /Delete Cluster/i })).toBeInTheDocument();
    });

    it('does not render Delete Cluster button for approved status', () => {
      mockUseCluster.mockReturnValue(
        defaultMockCluster(defaultPages, { status: 'approved' })
      );

      render(<ClusterDetailPage />);

      expect(screen.queryByRole('button', { name: /Delete Cluster/i })).not.toBeInTheDocument();
    });

    it('shows Confirm Delete on first click', async () => {
      const user = userEvent.setup();
      render(<ClusterDetailPage />);

      await user.click(screen.getByRole('button', { name: /Delete Cluster/i }));

      expect(screen.getByRole('button', { name: /Confirm Delete/i })).toBeInTheDocument();
    });

    it('calls deleteCluster on second click', async () => {
      const user = userEvent.setup();
      render(<ClusterDetailPage />);

      const deleteBtn = screen.getByRole('button', { name: /Delete Cluster/i });
      await user.click(deleteBtn);
      await user.click(screen.getByRole('button', { name: /Confirm Delete/i }));

      expect(mockDeleteClusterMutate).toHaveBeenCalledWith(
        { projectId: 'test-project-123', clusterId: 'cluster-456' },
        expect.objectContaining({
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        })
      );
    });
  });
});
