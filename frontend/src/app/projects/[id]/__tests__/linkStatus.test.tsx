import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ProjectDetailPage from '../page';

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

const mockUseStartBrandConfigGeneration = vi.fn();
const mockUseBrandConfigGeneration = vi.fn();
vi.mock('@/hooks/useBrandConfigGeneration', () => ({
  useStartBrandConfigGeneration: () => mockUseStartBrandConfigGeneration(),
  useBrandConfigGeneration: () => mockUseBrandConfigGeneration(),
}));

const mockUseCrawlStatus = vi.fn();
vi.mock('@/hooks/use-crawl-status', () => ({
  useCrawlStatus: () => mockUseCrawlStatus(),
  getOnboardingStep: () => ({ currentStep: 'content' as const, hasStarted: true }),
}));

const mockUseClusters = vi.fn();
vi.mock('@/hooks/useClusters', () => ({
  useClusters: () => mockUseClusters(),
}));

const mockUseLinkMap = vi.fn();
const mockUsePlanStatus = vi.fn();
vi.mock('@/hooks/useLinks', () => ({
  useLinkMap: (...args: unknown[]) => mockUseLinkMap(...args),
  usePlanStatus: (...args: unknown[]) => mockUsePlanStatus(...args),
}));

// ============================================================================
// Default mock setup
// ============================================================================
const mockProject = {
  id: 'test-project-123',
  name: 'Test Project',
  site_url: 'https://example.com',
  brand_config_status: 'pending' as const,
  has_brand_config: false,
  uploaded_files_count: 0,
};

const defaultBrandGen = {
  isGenerating: false,
  progress: 0,
};

// ============================================================================
// Tests
// ============================================================================
describe('ProjectDetailPage - Link Status Indicators', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    mockUseProject.mockReturnValue({ data: mockProject, isLoading: false, error: null });
    mockUseDeleteProject.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    mockUseBrandConfigGeneration.mockReturnValue(defaultBrandGen);
    mockUseStartBrandConfigGeneration.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    mockUseCrawlStatus.mockReturnValue({
      data: {
        status: 'complete',
        progress: { total: 5, completed: 5, failed: 0 },
        pages: [
          { labels: ['shoes'] },
          { labels: ['boots'] },
          { labels: ['sandals'] },
          { labels: ['sneakers'] },
          { labels: ['loafers'] },
        ],
      },
    });
    mockUseClusters.mockReturnValue({ data: [] });

    // Default: onboarding links not planned
    mockUseLinkMap.mockReturnValue({ data: null });
    mockUsePlanStatus.mockReturnValue({ data: null });
  });

  // --------------------------------------------------------------------------
  // Onboarding scope link status
  // --------------------------------------------------------------------------
  describe('onboarding link status', () => {
    it('shows "Links: Not planned" when no link data', () => {
      mockUseLinkMap.mockReturnValue({ data: null });
      mockUsePlanStatus.mockReturnValue({ data: null });
      render(<ProjectDetailPage />);
      expect(screen.getByText('Links: Not planned')).toBeInTheDocument();
    });

    it('shows "Links: N planned" when links exist', () => {
      mockUseLinkMap.mockReturnValue({
        data: { total_links: 15 },
      });
      mockUsePlanStatus.mockReturnValue({ data: { status: 'idle' } });
      render(<ProjectDetailPage />);
      expect(screen.getByText('Links: 15 planned')).toBeInTheDocument();
    });

    it('shows "Links: Planning..." when planning is in progress', () => {
      mockUseLinkMap.mockReturnValue({ data: null });
      mockUsePlanStatus.mockReturnValue({ data: { status: 'planning' } });
      render(<ProjectDetailPage />);
      expect(screen.getByText('Links: Planning...')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Cluster link status
  // --------------------------------------------------------------------------
  describe('cluster link status', () => {
    it('shows link status badges on cluster cards', () => {
      mockUseClusters.mockReturnValue({
        data: [
          { id: 'cluster-1', name: 'Running Shoes', seed_keyword: 'running shoes', page_count: 5, status: 'approved' },
        ],
      });
      // useLinkMap is called for both onboarding and cluster scopes, both return links
      mockUseLinkMap.mockReturnValue({ data: { total_links: 8 } });
      mockUsePlanStatus.mockReturnValue({ data: { status: 'idle' } });
      render(<ProjectDetailPage />);
      // The cluster card should appear
      expect(screen.getByText('Running Shoes')).toBeInTheDocument();
      // Link status badge should appear (may be multiple: onboarding + cluster)
      const badges = screen.getAllByText('Links: 8 planned');
      expect(badges.length).toBeGreaterThanOrEqual(1);
    });

    it('shows "Links: Not planned" on cluster with no links', () => {
      mockUseClusters.mockReturnValue({
        data: [
          { id: 'cluster-1', name: 'Hiking Boots', seed_keyword: 'hiking boots', page_count: 3, status: 'approved' },
        ],
      });
      mockUseLinkMap.mockReturnValue({ data: null });
      mockUsePlanStatus.mockReturnValue({ data: null });
      render(<ProjectDetailPage />);
      // Multiple "Links: Not planned" badges (onboarding + cluster)
      const badges = screen.getAllByText('Links: Not planned');
      expect(badges.length).toBeGreaterThanOrEqual(2);
    });
  });
});
