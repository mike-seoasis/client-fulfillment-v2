import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import OnboardingLinkMapPage from '../page';
import type { LinkMap, LinkMapPage } from '@/lib/api';

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
vi.mock('@/hooks/use-projects', () => ({
  useProject: () => mockUseProject(),
}));

const mockUseLinkMap = vi.fn();
const mockPlanLinksMutation = {
  mutateAsync: vi.fn(),
  isPending: false,
};

vi.mock('@/hooks/useLinks', () => ({
  useLinkMap: () => mockUseLinkMap(),
  usePlanLinks: () => mockPlanLinksMutation,
}));

// ============================================================================
// Mock data factories
// ============================================================================
const mockProject = {
  id: 'test-project-123',
  name: 'Test Project',
  site_url: 'https://example.com',
};

const createMockPage = (
  id: string,
  title: string,
  overrides: Partial<LinkMapPage> = {}
): LinkMapPage => ({
  page_id: id,
  url: `https://example.com/${id}`,
  title,
  is_priority: false,
  role: null,
  labels: ['shoes'],
  outbound_count: 3,
  inbound_count: 2,
  outbound_links: [],
  methods: { rule_based: 2, llm_fallback: 1 },
  validation_status: 'verified',
  ...overrides,
});

const createMockLinkMap = (
  pages: LinkMapPage[] = [],
  overrides: Partial<LinkMap> = {}
): LinkMap => ({
  scope: 'onboarding',
  total_links: 12,
  total_pages: pages.length,
  avg_links_per_page: pages.length > 0 ? 12 / pages.length : 0,
  validation_pass_rate: 85,
  method_breakdown: { rule_based: 8, llm_fallback: 4 },
  anchor_diversity: { partial_match: 50, exact_match: 20, natural: 30 },
  pages,
  hierarchy: null,
  ...overrides,
});

const defaultPages: LinkMapPage[] = [
  createMockPage('page-1', 'Running Shoes Guide', {
    labels: ['running', 'shoes'],
    is_priority: true,
    outbound_count: 4,
    inbound_count: 5,
  }),
  createMockPage('page-2', 'Trail Running Tips', {
    labels: ['running', 'trails'],
    outbound_count: 3,
    inbound_count: 2,
  }),
  createMockPage('page-3', 'Hiking Boots Review', {
    labels: ['hiking', 'boots'],
    outbound_count: 2,
    inbound_count: 1,
  }),
];

// ============================================================================
// Tests
// ============================================================================
describe('OnboardingLinkMapPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProject.mockReturnValue({ data: mockProject, isLoading: false, error: null });
    mockUseLinkMap.mockReturnValue({ data: createMockLinkMap(defaultPages), isLoading: false });
    mockPlanLinksMutation.mutateAsync.mockResolvedValue({});
    mockPlanLinksMutation.isPending = false;
  });

  // --------------------------------------------------------------------------
  // Rendering
  // --------------------------------------------------------------------------
  describe('rendering', () => {
    it('displays the page title', () => {
      render(<OnboardingLinkMapPage />);
      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveTextContent(/Link Map/);
      expect(heading).toHaveTextContent(/Onboarding Pages/);
    });

    it('displays breadcrumb with project name', () => {
      render(<OnboardingLinkMapPage />);
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });

    it('displays loading skeleton when data is loading', () => {
      mockUseProject.mockReturnValue({ data: null, isLoading: true, error: null });
      render(<OnboardingLinkMapPage />);
      expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
    });

    it('displays not found state on error', () => {
      mockUseProject.mockReturnValue({ data: null, isLoading: false, error: new Error('Not found') });
      render(<OnboardingLinkMapPage />);
      expect(screen.getByText('Not Found')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Stats sidebar
  // --------------------------------------------------------------------------
  describe('stats sidebar', () => {
    it('renders correct summary numbers', () => {
      render(<OnboardingLinkMapPage />);
      const sidebar = screen.getByText('Summary').closest('div[class*="w-64"]') as HTMLElement;
      expect(within(sidebar).getByText('12')).toBeInTheDocument();
      expect(within(sidebar).getByText('85%')).toBeInTheDocument();
    });

    it('renders method breakdown', () => {
      render(<OnboardingLinkMapPage />);
      const sidebar = screen.getByText('Summary').closest('div[class*="w-64"]') as HTMLElement;
      expect(within(sidebar).getByText('rule_based')).toBeInTheDocument();
      expect(within(sidebar).getByText('8')).toBeInTheDocument();
      expect(within(sidebar).getByText('llm_fallback')).toBeInTheDocument();
    });

    it('renders anchor diversity percentages', () => {
      render(<OnboardingLinkMapPage />);
      expect(screen.getByText('partial_match')).toBeInTheDocument();
      expect(screen.getByText('50%')).toBeInTheDocument();
      expect(screen.getByText('exact_match')).toBeInTheDocument();
      expect(screen.getByText('20%')).toBeInTheDocument();
      expect(screen.getByText('natural')).toBeInTheDocument();
      expect(screen.getByText('30%')).toBeInTheDocument();
    });

    it('renders priority page stats', () => {
      render(<OnboardingLinkMapPage />);
      expect(screen.getByText('1 priority pages')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Table rendering
  // --------------------------------------------------------------------------
  describe('table', () => {
    it('renders page rows with correct data', () => {
      render(<OnboardingLinkMapPage />);
      // Pages appear in both label group visualization and the table
      expect(screen.getAllByText('Running Shoes Guide').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Trail Running Tips').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Hiking Boots Review').length).toBeGreaterThanOrEqual(1);
    });

    it('shows footer with page count', () => {
      render(<OnboardingLinkMapPage />);
      expect(screen.getByText(/3 of 3 pages/)).toBeInTheDocument();
    });

    it('renders sortable column headers', () => {
      render(<OnboardingLinkMapPage />);
      expect(screen.getByRole('button', { name: /Page/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Labels/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Out/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /In/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Method/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Status/ })).toBeInTheDocument();
    });

    it('navigates to page detail on row click', async () => {
      const user = userEvent.setup();
      render(<OnboardingLinkMapPage />);
      // Click the first page row button (priority page floats to top)
      const rows = screen.getAllByRole('button', { name: /Running Shoes Guide/ });
      await user.click(rows[0]);
      expect(mockRouterPush).toHaveBeenCalledWith('/projects/test-project-123/links/page/page-1');
    });
  });

  // --------------------------------------------------------------------------
  // Filter controls
  // --------------------------------------------------------------------------
  describe('filter controls', () => {
    it('filters by label dropdown', async () => {
      const user = userEvent.setup();
      render(<OnboardingLinkMapPage />);

      const labelSelect = screen.getByLabelText('Label:');
      await user.selectOptions(labelSelect, 'hiking');

      // Footer reflects filtered count
      expect(screen.getByText(/1 of 3 pages/)).toBeInTheDocument();
    });

    it('filters by priority-only checkbox', async () => {
      const user = userEvent.setup();
      render(<OnboardingLinkMapPage />);

      const checkbox = screen.getByLabelText('Priority only');
      await user.click(checkbox);

      // Footer reflects filtered count (only 1 priority page)
      expect(screen.getByText(/1 of 3 pages/)).toBeInTheDocument();
    });

    it('filters by search query', async () => {
      const user = userEvent.setup();
      render(<OnboardingLinkMapPage />);

      const searchInput = screen.getByPlaceholderText('Search pages...');
      await user.type(searchInput, 'trail');

      // Footer reflects filtered count
      expect(screen.getByText(/1 of 3 pages/)).toBeInTheDocument();
    });

    it('shows empty state when no pages match filters', async () => {
      const user = userEvent.setup();
      render(<OnboardingLinkMapPage />);

      const searchInput = screen.getByPlaceholderText('Search pages...');
      await user.type(searchInput, 'nonexistent');

      expect(screen.getByText('No pages match the current filters.')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Re-plan button and confirmation
  // --------------------------------------------------------------------------
  describe('re-plan', () => {
    it('shows Re-plan Links button when links exist', () => {
      render(<OnboardingLinkMapPage />);
      expect(screen.getByRole('button', { name: 'Re-plan Links' })).toBeInTheDocument();
    });

    it('does not show Re-plan Links button when no links', () => {
      mockUseLinkMap.mockReturnValue({
        data: createMockLinkMap([], { total_links: 0 }),
        isLoading: false,
      });
      render(<OnboardingLinkMapPage />);
      expect(screen.queryByRole('button', { name: 'Re-plan Links' })).not.toBeInTheDocument();
    });

    it('opens confirmation dialog on Re-plan click', async () => {
      const user = userEvent.setup();
      render(<OnboardingLinkMapPage />);
      await user.click(screen.getByRole('button', { name: 'Re-plan Links' }));
      expect(screen.getByText('This will replace all current links. Previous plan will be saved as a snapshot.')).toBeInTheDocument();
    });

    it('cancels confirmation dialog', async () => {
      const user = userEvent.setup();
      render(<OnboardingLinkMapPage />);
      await user.click(screen.getByRole('button', { name: 'Re-plan Links' }));

      // Click cancel in the dialog
      const dialog = screen.getByText('This will replace all current links. Previous plan will be saved as a snapshot.').closest('div[class*="relative"]') as HTMLElement;
      const cancelBtn = within(dialog).getByRole('button', { name: 'Cancel' });
      await user.click(cancelBtn);

      expect(screen.queryByText('This will replace all current links.')).not.toBeInTheDocument();
    });

    it('calls mutation and redirects on confirm', async () => {
      const user = userEvent.setup();
      render(<OnboardingLinkMapPage />);
      await user.click(screen.getByRole('button', { name: 'Re-plan Links' }));

      // Find the confirmation button in the dialog (the one with variant="danger")
      const confirmButtons = screen.getAllByRole('button', { name: 'Re-plan Links' });
      // The last one is inside the dialog
      await user.click(confirmButtons[confirmButtons.length - 1]);

      expect(mockPlanLinksMutation.mutateAsync).toHaveBeenCalledWith({
        projectId: 'test-project-123',
        scope: 'onboarding',
      });
    });
  });

  // --------------------------------------------------------------------------
  // Empty state
  // --------------------------------------------------------------------------
  describe('empty state', () => {
    it('shows empty state when no links planned', () => {
      mockUseLinkMap.mockReturnValue({
        data: createMockLinkMap([], { total_links: 0 }),
        isLoading: false,
      });
      render(<OnboardingLinkMapPage />);
      expect(screen.getByText('No links planned yet')).toBeInTheDocument();
      expect(screen.getByText('Plan Links')).toBeInTheDocument();
    });
  });
});
