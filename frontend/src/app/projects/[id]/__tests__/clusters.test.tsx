import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ProjectDetailPage from '../page';
import type { ClusterListItem } from '@/lib/api';

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
const mockUseProject = vi.fn();
const mockUseDeleteProject = vi.fn();
vi.mock('@/hooks/use-projects', () => ({
  useProject: () => mockUseProject(),
  useDeleteProject: () => mockUseDeleteProject(),
}));

const mockUseBrandConfigGeneration = vi.fn();
const mockUseStartBrandConfigGeneration = vi.fn();
vi.mock('@/hooks/useBrandConfigGeneration', () => ({
  useBrandConfigGeneration: () => mockUseBrandConfigGeneration(),
  useStartBrandConfigGeneration: () => mockUseStartBrandConfigGeneration(),
}));

const mockUseCrawlStatus = vi.fn();
vi.mock('@/hooks/use-crawl-status', () => ({
  useCrawlStatus: () => mockUseCrawlStatus(),
  getOnboardingStep: () => ({
    currentStep: 'upload',
    stepIndex: 0,
    hasStarted: false,
  }),
}));

const mockUseClusters = vi.fn();
vi.mock('@/hooks/useClusters', () => ({
  useClusters: () => mockUseClusters(),
}));

const mockUseBlogCampaigns = vi.fn();
vi.mock('@/hooks/useBlogs', () => ({
  useBlogCampaigns: (...args: unknown[]) => mockUseBlogCampaigns(...args),
}));

const mockUseLinkMap = vi.fn();
const mockUsePlanStatus = vi.fn();
vi.mock('@/hooks/useLinks', () => ({
  useLinkMap: (...args: unknown[]) => mockUseLinkMap(...args),
  usePlanStatus: (...args: unknown[]) => mockUsePlanStatus(...args),
}));

// ============================================================================
// Default mock values
// ============================================================================
const mockProject = {
  id: 'test-project-123',
  name: 'Test Project',
  site_url: 'https://example.com',
  client_id: null,
  additional_info: null,
  status: 'active',
  phase_status: {},
  brand_config_status: 'pending',
  has_brand_config: false,
  uploaded_files_count: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-15T10:30:00Z',
};

const defaultMockProject = () => ({
  data: mockProject,
  isLoading: false,
  error: null,
});

const defaultMockDeleteProject = () => ({
  mutateAsync: vi.fn(),
  isPending: false,
});

const defaultMockBrandConfig = () => ({
  isGenerating: false,
  progress: 0,
  status: null,
  data: null,
  isLoading: false,
  error: null,
});

const defaultMockStartBrandConfig = () => ({
  mutateAsync: vi.fn(),
  isPending: false,
});

const defaultMockCrawlStatus = () => ({
  data: null,
  isLoading: false,
  error: null,
});

// ============================================================================
// Mock cluster data helpers
// ============================================================================
const createMockClusterListItem = (
  id: string,
  name: string,
  seedKeyword: string,
  status: string,
  pageCount: number,
  approvedCount = 0
): ClusterListItem => ({
  id,
  name,
  seed_keyword: seedKeyword,
  status,
  page_count: pageCount,
  approved_count: approvedCount,
  created_at: '2026-01-15T10:00:00Z',
});

// ============================================================================
// Tests
// ============================================================================
describe('ProjectDetailPage - Cluster Section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProject.mockReturnValue(defaultMockProject());
    mockUseDeleteProject.mockReturnValue(defaultMockDeleteProject());
    mockUseBrandConfigGeneration.mockReturnValue(defaultMockBrandConfig());
    mockUseStartBrandConfigGeneration.mockReturnValue(defaultMockStartBrandConfig());
    mockUseCrawlStatus.mockReturnValue(defaultMockCrawlStatus());
    mockUseClusters.mockReturnValue({ data: undefined, isLoading: false, error: null });
    mockUseBlogCampaigns.mockReturnValue({ data: undefined, isLoading: false, error: null });
    mockUseLinkMap.mockReturnValue({ data: undefined, isLoading: false });
    mockUsePlanStatus.mockReturnValue({ data: undefined, isLoading: false });
  });

  // ============================================================================
  // Empty state
  // ============================================================================
  describe('empty state', () => {
    it('shows "No clusters yet" when no clusters exist', () => {
      mockUseClusters.mockReturnValue({ data: [], isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText('No clusters yet')).toBeInTheDocument();
    });

    it('shows "No clusters yet" when clusters is undefined', () => {
      mockUseClusters.mockReturnValue({ data: undefined, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText('No clusters yet')).toBeInTheDocument();
    });

    it('shows "+ New Cluster" link in empty state', () => {
      mockUseClusters.mockReturnValue({ data: [], isLoading: false, error: null });

      render(<ProjectDetailPage />);

      // The empty state + New Cluster renders as a ButtonLink (<a>), not a <button>
      const newClusterLink = screen.getByRole('link', { name: /New Cluster/i });
      expect(newClusterLink).toBeInTheDocument();
    });

    it('links New Cluster button to correct URL in empty state', () => {
      mockUseClusters.mockReturnValue({ data: [], isLoading: false, error: null });

      render(<ProjectDetailPage />);

      const newClusterLink = screen.getByText('+ New Cluster').closest('a');
      expect(newClusterLink).toHaveAttribute('href', '/projects/test-project-123/clusters/new');
    });
  });

  // ============================================================================
  // Cluster cards rendering
  // ============================================================================
  describe('cluster cards rendering', () => {
    it('renders cluster cards with correct data', () => {
      const clusters = [
        createMockClusterListItem('c1', 'Running Shoes', 'running shoes', 'suggestions_ready', 8, 3),
        createMockClusterListItem('c2', 'Hiking Boots', 'hiking boots', 'approved', 5, 5),
      ];
      mockUseClusters.mockReturnValue({ data: clusters, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText('Running Shoes')).toBeInTheDocument();
      expect(screen.getByText('Hiking Boots')).toBeInTheDocument();
    });

    it('displays approved count of page count for each cluster', () => {
      const clusters = [
        createMockClusterListItem('c1', 'Running Shoes', 'running shoes', 'suggestions_ready', 8, 3),
      ];
      mockUseClusters.mockReturnValue({ data: clusters, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText(/3 of 8/)).toBeInTheDocument();
      expect(screen.getByText(/pages approved/)).toBeInTheDocument();
    });

    it('displays singular "page" when count is 1', () => {
      const clusters = [
        createMockClusterListItem('c1', 'Single Page Cluster', 'test', 'generating', 1, 1),
      ];
      mockUseClusters.mockReturnValue({ data: clusters, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText(/1 of 1/)).toBeInTheDocument();
      expect(screen.getByText(/page approved/)).toBeInTheDocument();
    });

    it('falls back to seed_keyword when name is empty', () => {
      const clusters = [
        createMockClusterListItem('c1', '', 'trail running shoes', 'suggestions_ready', 5),
      ];
      mockUseClusters.mockReturnValue({ data: clusters, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText('trail running shoes')).toBeInTheDocument();
    });

    it('displays status badge for each cluster', () => {
      const clusters = [
        createMockClusterListItem('c1', 'Cluster A', 'seed a', 'suggestions_ready', 5),
        createMockClusterListItem('c2', 'Cluster B', 'seed b', 'approved', 3),
        createMockClusterListItem('c3', 'Cluster C', 'seed c', 'complete', 7),
      ];
      mockUseClusters.mockReturnValue({ data: clusters, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText('Awaiting Approval')).toBeInTheDocument();
      expect(screen.getByText('Approved')).toBeInTheDocument();
      expect(screen.getByText('Complete')).toBeInTheDocument();
    });

    it('displays Generating status badge', () => {
      const clusters = [
        createMockClusterListItem('c1', 'Cluster A', 'seed a', 'generating', 0),
      ];
      mockUseClusters.mockReturnValue({ data: clusters, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText('Generating')).toBeInTheDocument();
    });

    it('displays Generating Content status badge', () => {
      const clusters = [
        createMockClusterListItem('c1', 'Cluster A', 'seed a', 'content_generating', 5),
      ];
      mockUseClusters.mockReturnValue({ data: clusters, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText('Generating Content')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Click navigation
  // ============================================================================
  describe('click navigation', () => {
    it('cluster cards link to cluster detail page', () => {
      const clusters = [
        createMockClusterListItem('c1', 'Running Shoes', 'running shoes', 'suggestions_ready', 8),
      ];
      mockUseClusters.mockReturnValue({ data: clusters, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      const clusterLink = screen.getByText('Running Shoes').closest('a');
      expect(clusterLink).toHaveAttribute(
        'href',
        '/projects/test-project-123/clusters/c1'
      );
    });
  });

  // ============================================================================
  // New Cluster button (when clusters exist)
  // ============================================================================
  describe('New Cluster button with existing clusters', () => {
    it('shows "+ New Cluster" link in header when clusters exist', () => {
      const clusters = [
        createMockClusterListItem('c1', 'Running Shoes', 'running shoes', 'suggestions_ready', 8),
      ];
      mockUseClusters.mockReturnValue({ data: clusters, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      const headerLink = screen.getByRole('link', { name: '+ New Cluster' });
      expect(headerLink).toBeInTheDocument();
    });

    it('header New Cluster link has correct URL', () => {
      const clusters = [
        createMockClusterListItem('c1', 'Running Shoes', 'running shoes', 'suggestions_ready', 8),
      ];
      mockUseClusters.mockReturnValue({ data: clusters, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      const headerLink = screen.getByRole('link', { name: '+ New Cluster' });
      expect(headerLink).toHaveAttribute('href', '/projects/test-project-123/clusters/new');
    });
  });

  // ============================================================================
  // Section header
  // ============================================================================
  describe('section header', () => {
    it('renders New Content section header', () => {
      render(<ProjectDetailPage />);

      expect(screen.getByText('New Content')).toBeInTheDocument();
    });

    it('renders Keyword Clusters badge', () => {
      render(<ProjectDetailPage />);

      expect(screen.getByText('Keyword Clusters')).toBeInTheDocument();
    });
  });
});
