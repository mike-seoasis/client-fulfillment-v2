import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ProjectDetailPage from '../page';
import type { BlogCampaignListItem } from '@/lib/api';

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
  useBlogCampaigns: () => mockUseBlogCampaigns(),
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
// Mock blog campaign data helpers
// ============================================================================
const createMockBlogCampaign = (
  id: string,
  name: string,
  status: string,
  clusterName: string,
  postCount: number,
  approvedCount = 0,
  contentCompleteCount = 0,
): BlogCampaignListItem => ({
  id,
  name,
  status,
  cluster_name: clusterName,
  post_count: postCount,
  approved_count: approvedCount,
  content_complete_count: contentCompleteCount,
  created_at: '2026-01-20T10:00:00Z',
});

// ============================================================================
// Tests
// ============================================================================
describe('ProjectDetailPage - Blog Section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProject.mockReturnValue(defaultMockProject());
    mockUseDeleteProject.mockReturnValue(defaultMockDeleteProject());
    mockUseBrandConfigGeneration.mockReturnValue(defaultMockBrandConfig());
    mockUseStartBrandConfigGeneration.mockReturnValue(defaultMockStartBrandConfig());
    mockUseCrawlStatus.mockReturnValue(defaultMockCrawlStatus());
    mockUseClusters.mockReturnValue({ data: [], isLoading: false, error: null });
    mockUseBlogCampaigns.mockReturnValue({ data: undefined, isLoading: false, error: null });
    mockUseLinkMap.mockReturnValue({ data: undefined, isLoading: false });
    mockUsePlanStatus.mockReturnValue({ data: undefined, isLoading: false });
  });

  // ============================================================================
  // Empty state
  // ============================================================================
  describe('empty state', () => {
    it('shows "No blog campaigns yet" when no campaigns exist', () => {
      mockUseBlogCampaigns.mockReturnValue({ data: [], isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText('No blog campaigns yet')).toBeInTheDocument();
    });

    it('shows "No blog campaigns yet" when campaigns is undefined', () => {
      mockUseBlogCampaigns.mockReturnValue({ data: undefined, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText('No blog campaigns yet')).toBeInTheDocument();
    });

    it('shows "+ New Campaign" link in empty state', () => {
      mockUseBlogCampaigns.mockReturnValue({ data: [], isLoading: false, error: null });

      render(<ProjectDetailPage />);

      const newCampaignLink = screen.getByRole('link', { name: /New Campaign/i });
      expect(newCampaignLink).toBeInTheDocument();
    });

    it('links New Campaign button to correct URL', () => {
      mockUseBlogCampaigns.mockReturnValue({ data: [], isLoading: false, error: null });

      render(<ProjectDetailPage />);

      const newCampaignLink = screen.getByText('+ New Campaign').closest('a');
      expect(newCampaignLink).toHaveAttribute('href', '/projects/test-project-123/blogs/new');
    });
  });

  // ============================================================================
  // Campaign cards rendering
  // ============================================================================
  describe('campaign cards rendering', () => {
    it('renders campaign cards with correct name and cluster_name', () => {
      const campaigns = [
        createMockBlogCampaign('b1', 'SEO Blog Series', 'planning', 'Running Shoes', 5, 0, 0),
        createMockBlogCampaign('b2', 'Product Guides', 'writing', 'Hiking Boots', 3, 0, 1),
      ];
      mockUseBlogCampaigns.mockReturnValue({ data: campaigns, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText('SEO Blog Series')).toBeInTheDocument();
      expect(screen.getByText('Running Shoes')).toBeInTheDocument();
      expect(screen.getByText('Product Guides')).toBeInTheDocument();
      expect(screen.getByText('Hiking Boots')).toBeInTheDocument();
    });

    it('displays post completion counts', () => {
      const campaigns = [
        createMockBlogCampaign('b1', 'SEO Blog Series', 'writing', 'Running Shoes', 8, 3, 2),
      ];
      mockUseBlogCampaigns.mockReturnValue({ data: campaigns, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText(/2 of 8/)).toBeInTheDocument();
      expect(screen.getByText(/posts done/)).toBeInTheDocument();
    });

    it('displays Planning status badge', () => {
      const campaigns = [
        createMockBlogCampaign('b1', 'Blog A', 'planning', 'Cluster A', 5),
      ];
      mockUseBlogCampaigns.mockReturnValue({ data: campaigns, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText('Planning')).toBeInTheDocument();
    });

    it('displays Complete status badge', () => {
      const campaigns = [
        createMockBlogCampaign('b1', 'Blog A', 'complete', 'Cluster A', 5, 5, 5),
      ];
      mockUseBlogCampaigns.mockReturnValue({ data: campaigns, isLoading: false, error: null });

      render(<ProjectDetailPage />);

      expect(screen.getByText('Complete')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Section header
  // ============================================================================
  describe('section header', () => {
    it('renders Blogs section header with Supporting Content badge', () => {
      render(<ProjectDetailPage />);

      expect(screen.getByText('Blogs')).toBeInTheDocument();
      expect(screen.getByText('Supporting Content')).toBeInTheDocument();
    });
  });
});
