import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PageLinkDetailPage from '../page';
import type { InternalLink, LinkMapPage, PageLinks } from '@/lib/api';

// ============================================================================
// Mock Next.js navigation
// ============================================================================
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'test-project-123', pageId: 'page-1' }),
}));

// ============================================================================
// Mock hooks
// ============================================================================
const mockUseProject = vi.fn();
vi.mock('@/hooks/use-projects', () => ({
  useProject: () => mockUseProject(),
}));

const mockUsePageLinks = vi.fn();
const mockUseLinkMap = vi.fn();
const mockAddLinkMutation = { mutateAsync: vi.fn(), isPending: false };
const mockRemoveLinkMutation = { mutateAsync: vi.fn(), isPending: false };
const mockEditLinkMutation = { mutateAsync: vi.fn(), isPending: false };
const mockUseAnchorSuggestions = vi.fn();

vi.mock('@/hooks/useLinks', () => ({
  usePageLinks: () => mockUsePageLinks(),
  useLinkMap: () => mockUseLinkMap(),
  useAddLink: () => mockAddLinkMutation,
  useRemoveLink: () => mockRemoveLinkMutation,
  useEditLink: () => mockEditLinkMutation,
  useAnchorSuggestions: (...args: unknown[]) => mockUseAnchorSuggestions(...args),
}));

// ============================================================================
// Mock data factories
// ============================================================================
const mockProject = {
  id: 'test-project-123',
  name: 'Test Project',
  site_url: 'https://example.com',
};

const createMockLink = (
  id: string,
  overrides: Partial<InternalLink> = {}
): InternalLink => ({
  id,
  source_page_id: 'page-1',
  target_page_id: 'page-2',
  target_url: 'https://example.com/page-2',
  target_title: 'Target Page',
  target_keyword: 'target keyword',
  anchor_text: 'click here',
  anchor_type: 'partial_match',
  position_in_content: 2,
  is_mandatory: false,
  placement_method: 'rule_based',
  status: 'verified',
  ...overrides,
});

const createMockPageLinks = (overrides: Partial<PageLinks> = {}): PageLinks => ({
  outbound_links: [
    createMockLink('link-1', {
      target_page_id: 'page-2',
      target_title: 'Trail Running Tips',
      anchor_text: 'trail running',
      anchor_type: 'partial_match',
    }),
    createMockLink('link-2', {
      target_page_id: 'page-3',
      target_title: 'Hiking Boots Guide',
      anchor_text: 'hiking boots',
      anchor_type: 'exact_match',
      is_mandatory: true,
    }),
  ],
  inbound_links: [
    createMockLink('link-3', {
      source_page_id: 'page-4',
      target_page_id: 'page-1',
      anchor_text: 'running shoes',
      anchor_type: 'natural',
    }),
  ],
  anchor_diversity: { partial_match: 50, exact_match: 25, natural: 25 },
  diversity_score: 'good',
  ...overrides,
});

const createMockLinkMapPage = (
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
  methods: { rule_based: 2 },
  validation_status: 'verified',
  ...overrides,
});

const defaultLinkMapData = {
  scope: 'onboarding',
  total_links: 10,
  total_pages: 4,
  avg_links_per_page: 2.5,
  validation_pass_rate: 90,
  method_breakdown: { rule_based: 7, llm_fallback: 3 },
  anchor_diversity: { partial_match: 60, exact_match: 20, natural: 20 },
  pages: [
    createMockLinkMapPage('page-1', 'Running Shoes Guide', { is_priority: true }),
    createMockLinkMapPage('page-2', 'Trail Running Tips'),
    createMockLinkMapPage('page-3', 'Hiking Boots Guide'),
    createMockLinkMapPage('page-4', 'Walking Shoes Review'),
  ],
  hierarchy: null,
};

// ============================================================================
// Tests
// ============================================================================
describe('PageLinkDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProject.mockReturnValue({ data: mockProject, isLoading: false, error: null });
    mockUsePageLinks.mockReturnValue({ data: createMockPageLinks(), isLoading: false });
    mockUseLinkMap.mockReturnValue({ data: defaultLinkMapData, isLoading: false });
    mockAddLinkMutation.mutateAsync.mockResolvedValue({});
    mockAddLinkMutation.isPending = false;
    mockRemoveLinkMutation.mutateAsync.mockResolvedValue({});
    mockRemoveLinkMutation.isPending = false;
    mockEditLinkMutation.mutateAsync.mockResolvedValue({});
    mockEditLinkMutation.isPending = false;
    mockUseAnchorSuggestions.mockReturnValue({ data: null });
  });

  // --------------------------------------------------------------------------
  // Rendering
  // --------------------------------------------------------------------------
  describe('rendering', () => {
    it('displays breadcrumb with project and link map', () => {
      render(<PageLinkDetailPage />);
      expect(screen.getByText('Test Project')).toBeInTheDocument();
      expect(screen.getByText('Link Map')).toBeInTheDocument();
    });

    it('displays loading skeleton when data is loading', () => {
      mockUseProject.mockReturnValue({ data: null, isLoading: true, error: null });
      render(<PageLinkDetailPage />);
      expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
    });

    it('displays not found state on error', () => {
      mockUseProject.mockReturnValue({ data: null, isLoading: false, error: new Error('Not found') });
      render(<PageLinkDetailPage />);
      expect(screen.getByText('Not Found')).toBeInTheDocument();
    });

    it('displays back to link map button', () => {
      render(<PageLinkDetailPage />);
      expect(screen.getByText('Back to Link Map')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Outbound links
  // --------------------------------------------------------------------------
  describe('outbound links', () => {
    it('renders outbound links count', () => {
      render(<PageLinkDetailPage />);
      expect(screen.getByText('Outbound Links (2)')).toBeInTheDocument();
    });

    it('renders outbound link details', () => {
      render(<PageLinkDetailPage />);
      expect(screen.getByText(/Trail Running Tips/)).toBeInTheDocument();
      expect(screen.getByText(/trail running/)).toBeInTheDocument();
      expect(screen.getByText(/Hiking Boots Guide/)).toBeInTheDocument();
    });

    it('renders anchor type badges', () => {
      render(<PageLinkDetailPage />);
      expect(screen.getByText('partial')).toBeInTheDocument();
      expect(screen.getByText('exact')).toBeInTheDocument();
    });

    it('shows mandatory badge for mandatory links', () => {
      render(<PageLinkDetailPage />);
      expect(screen.getByText('mandatory')).toBeInTheDocument();
    });

    it('does not show Remove button for mandatory links', () => {
      render(<PageLinkDetailPage />);
      // Should only be one Remove button (for the non-mandatory link)
      const removeButtons = screen.getAllByRole('button', { name: 'Remove' });
      expect(removeButtons).toHaveLength(1);
    });

    it('shows Edit Anchor button for all links', () => {
      render(<PageLinkDetailPage />);
      const editButtons = screen.getAllByRole('button', { name: 'Edit Anchor' });
      expect(editButtons).toHaveLength(2);
    });

    it('shows Add button in outbound section header', () => {
      render(<PageLinkDetailPage />);
      expect(screen.getByRole('button', { name: '+ Add' })).toBeInTheDocument();
    });

    it('shows empty state when no outbound links', () => {
      mockUsePageLinks.mockReturnValue({
        data: createMockPageLinks({ outbound_links: [], inbound_links: [] }),
        isLoading: false,
      });
      render(<PageLinkDetailPage />);
      expect(screen.getByText(/No outbound links yet/)).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Inbound links
  // --------------------------------------------------------------------------
  describe('inbound links', () => {
    it('renders inbound links count', () => {
      render(<PageLinkDetailPage />);
      expect(screen.getByText('Inbound Links (1)')).toBeInTheDocument();
    });

    it('renders inbound link source from page title map', () => {
      render(<PageLinkDetailPage />);
      expect(screen.getByText('Walking Shoes Review')).toBeInTheDocument();
    });

    it('renders inbound link anchor text and type', () => {
      render(<PageLinkDetailPage />);
      const inboundSection = screen.getByText('Inbound Links (1)').closest('div[class*="bg-white"]') as HTMLElement;
      expect(within(inboundSection).getByText(/running shoes/)).toBeInTheDocument();
      expect(within(inboundSection).getByText('natural')).toBeInTheDocument();
    });

    it('shows empty state when no inbound links', () => {
      mockUsePageLinks.mockReturnValue({
        data: createMockPageLinks({ inbound_links: [] }),
        isLoading: false,
      });
      render(<PageLinkDetailPage />);
      expect(screen.getByText('No inbound links to this page.')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Add Link modal
  // --------------------------------------------------------------------------
  describe('Add Link modal', () => {
    it('opens modal on Add button click', async () => {
      const user = userEvent.setup();
      render(<PageLinkDetailPage />);
      await user.click(screen.getByRole('button', { name: '+ Add' }));
      expect(screen.getByText('Add Internal Link')).toBeInTheDocument();
    });

    it('shows target page search field', async () => {
      const user = userEvent.setup();
      render(<PageLinkDetailPage />);
      await user.click(screen.getByRole('button', { name: '+ Add' }));
      expect(screen.getByPlaceholderText('Search pages in this silo...')).toBeInTheDocument();
    });

    it('filters out self and existing targets from available pages', async () => {
      const user = userEvent.setup();
      render(<PageLinkDetailPage />);
      await user.click(screen.getByRole('button', { name: '+ Add' }));

      // page-1 is self (should be excluded)
      // page-2 and page-3 are existing targets (should be excluded)
      // page-4 is available
      const availablePageButtons = screen.getAllByRole('button', { name: 'Walking Shoes Review' });
      expect(availablePageButtons.length).toBeGreaterThanOrEqual(1);
    });

    it('validates target page is required', async () => {
      const user = userEvent.setup();
      render(<PageLinkDetailPage />);
      await user.click(screen.getByRole('button', { name: '+ Add' }));

      // Type anchor text but don't select target
      await user.type(screen.getByPlaceholderText('Enter anchor text...'), 'some anchor');
      await user.click(screen.getByRole('button', { name: 'Add Link' }));

      expect(screen.getByText('Please select a target page.')).toBeInTheDocument();
      expect(mockAddLinkMutation.mutateAsync).not.toHaveBeenCalled();
    });

    it('validates anchor text is required', async () => {
      const user = userEvent.setup();
      render(<PageLinkDetailPage />);
      await user.click(screen.getByRole('button', { name: '+ Add' }));

      // Select a target page
      await user.click(screen.getByRole('button', { name: 'Walking Shoes Review' }));
      // Click Add Link without entering anchor text
      await user.click(screen.getByRole('button', { name: 'Add Link' }));

      expect(screen.getByText('Please enter anchor text.')).toBeInTheDocument();
      expect(mockAddLinkMutation.mutateAsync).not.toHaveBeenCalled();
    });

    it('closes modal on Cancel click', async () => {
      const user = userEvent.setup();
      render(<PageLinkDetailPage />);
      await user.click(screen.getByRole('button', { name: '+ Add' }));
      expect(screen.getByText('Add Internal Link')).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: 'Cancel' }));
      expect(screen.queryByText('Add Internal Link')).not.toBeInTheDocument();
    });

    it('shows anchor suggestions when target is selected', async () => {
      mockUseAnchorSuggestions.mockReturnValue({
        data: {
          primary_keyword: 'walking shoes',
          pop_variations: ['best walking shoes', 'comfortable walking shoes'],
          usage_counts: { 'walking shoes': 1 },
        },
      });
      const user = userEvent.setup();
      render(<PageLinkDetailPage />);
      await user.click(screen.getByRole('button', { name: '+ Add' }));

      // Select a target page
      await user.click(screen.getByRole('button', { name: 'Walking Shoes Review' }));

      // Should see suggestions section
      await waitFor(() => {
        expect(screen.getByText(/Suggested anchors/)).toBeInTheDocument();
        expect(screen.getByText(/best walking shoes/)).toBeInTheDocument();
      });
    });
  });

  // --------------------------------------------------------------------------
  // Edit Anchor modal
  // --------------------------------------------------------------------------
  describe('Edit Anchor modal', () => {
    it('opens edit modal on Edit Anchor button click', async () => {
      const user = userEvent.setup();
      render(<PageLinkDetailPage />);
      const editButtons = screen.getAllByRole('button', { name: 'Edit Anchor' });
      await user.click(editButtons[0]);
      expect(screen.getByText('Edit Anchor Text')).toBeInTheDocument();
    });

    it('shows current anchor text in edit modal', async () => {
      const user = userEvent.setup();
      render(<PageLinkDetailPage />);
      const editButtons = screen.getAllByRole('button', { name: 'Edit Anchor' });
      await user.click(editButtons[0]);
      const input = screen.getByDisplayValue('trail running');
      expect(input).toBeInTheDocument();
    });

    it('shows target name in edit modal', async () => {
      const user = userEvent.setup();
      render(<PageLinkDetailPage />);
      const editButtons = screen.getAllByRole('button', { name: 'Edit Anchor' });
      await user.click(editButtons[0]);
      expect(screen.getByText('Trail Running Tips')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Remove link confirmation
  // --------------------------------------------------------------------------
  describe('remove link', () => {
    it('opens confirm dialog on Remove click', async () => {
      const user = userEvent.setup();
      render(<PageLinkDetailPage />);
      await user.click(screen.getByRole('button', { name: 'Remove' }));
      // Dialog shows the confirmation message
      expect(screen.getByText(/Remove the link to/)).toBeInTheDocument();
      // Dialog has a heading "Remove Link"
      const headings = screen.getAllByText('Remove Link');
      expect(headings.length).toBeGreaterThanOrEqual(1);
    });

    it('calls remove mutation on confirm', async () => {
      const user = userEvent.setup();
      render(<PageLinkDetailPage />);
      await user.click(screen.getByRole('button', { name: 'Remove' }));

      // Find the confirm button in the dialog
      const confirmButton = screen.getAllByRole('button', { name: 'Remove Link' });
      await user.click(confirmButton[confirmButton.length - 1]);

      expect(mockRemoveLinkMutation.mutateAsync).toHaveBeenCalledWith({
        projectId: 'test-project-123',
        linkId: 'link-1',
      });
    });

    it('cancels remove dialog', async () => {
      const user = userEvent.setup();
      render(<PageLinkDetailPage />);
      await user.click(screen.getByRole('button', { name: 'Remove' }));
      await user.click(screen.getByRole('button', { name: 'Cancel' }));
      expect(screen.queryByText(/Remove the link to/)).not.toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Anchor Diversity section
  // --------------------------------------------------------------------------
  describe('anchor diversity', () => {
    it('renders diversity section title', () => {
      render(<PageLinkDetailPage />);
      expect(screen.getByText('Anchor Diversity for This Page (as target)')).toBeInTheDocument();
    });

    it('shows diversity score for inbound links', () => {
      render(<PageLinkDetailPage />);
      expect(screen.getByText(/Diversity score/)).toBeInTheDocument();
      // "High ✓" text in the score span
      expect(screen.getByText(/High/)).toBeInTheDocument();
    });

    it('shows no inbound message when empty', () => {
      mockUsePageLinks.mockReturnValue({
        data: createMockPageLinks({ inbound_links: [] }),
        isLoading: false,
      });
      render(<PageLinkDetailPage />);
      expect(screen.getByText('No inbound links to analyze.')).toBeInTheDocument();
    });
  });
});
