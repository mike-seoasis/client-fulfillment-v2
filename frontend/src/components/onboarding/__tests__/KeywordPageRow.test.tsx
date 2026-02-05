import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { KeywordPageRow } from '../KeywordPageRow';
import type { PageWithKeywords } from '@/lib/api';

// ============================================================================
// Mock hooks
// ============================================================================
const mockApproveKeyword = {
  mutateAsync: vi.fn(),
  isPending: false,
};

const mockTogglePriority = {
  mutateAsync: vi.fn(),
  isPending: false,
};

const mockUpdatePrimaryKeyword = {
  mutateAsync: vi.fn(),
  isPending: false,
};

vi.mock('@/hooks/useKeywordMutations', () => ({
  useApproveKeyword: () => mockApproveKeyword,
  useTogglePriority: () => mockTogglePriority,
  useUpdatePrimaryKeyword: () => mockUpdatePrimaryKeyword,
}));

// ============================================================================
// Mock data
// ============================================================================
const createMockPage = (overrides: Partial<PageWithKeywords> = {}): PageWithKeywords => ({
  id: 'page-123',
  url: 'https://example.com/products/running-shoes',
  title: 'Running Shoes Collection',
  labels: ['running-shoes', 'footwear'],
  product_count: 24,
  keywords: {
    id: 'kw-456',
    primary_keyword: 'running shoes',
    secondary_keywords: [],
    search_volume: 12500,
    difficulty_score: null,
    is_approved: false,
    is_priority: false,
    alternative_keywords: [
      { keyword: 'best running shoes', volume: 8000, cpc: null, competition: null, relevance_score: null, composite_score: 45.2 },
      { keyword: 'trail running shoes', volume: 5000, cpc: null, competition: null, relevance_score: null, composite_score: 42.1 },
    ],
    composite_score: 52.3,
    relevance_score: 0.85,
    ai_reasoning: null,
  },
  ...overrides,
});

const mockPageWithoutKeywords: PageWithKeywords = {
  id: 'page-789',
  url: 'https://example.com/about',
  title: 'About Us',
  labels: [],
  product_count: null,
  keywords: null,
};

const mockProjectId = 'project-abc';

// ============================================================================
// Unit Tests: KeywordPageRow rendering
// ============================================================================
describe('KeywordPageRow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApproveKeyword.isPending = false;
    mockTogglePriority.isPending = false;
    mockUpdatePrimaryKeyword.isPending = false;
  });

  describe('rendering', () => {
    it('renders page URL path (not full URL)', () => {
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByText('/products/running-shoes')).toBeInTheDocument();
    });

    it('renders page title', () => {
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByText('Running Shoes Collection')).toBeInTheDocument();
    });

    it('renders primary keyword', () => {
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByText('running shoes')).toBeInTheDocument();
    });

    it('renders search volume with comma formatting', () => {
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByText(/12,500 vol/)).toBeInTheDocument();
    });

    it('renders composite score', () => {
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByText(/52\.3 score/)).toBeInTheDocument();
    });

    it('shows dash for null search volume', () => {
      const page = createMockPage({
        keywords: {
          ...createMockPage().keywords!,
          search_volume: null,
        },
      });
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByText(/— vol/)).toBeInTheDocument();
    });

    it('shows dash for null composite score', () => {
      const page = createMockPage({
        keywords: {
          ...createMockPage().keywords!,
          composite_score: null,
        },
      });
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByText(/— score/)).toBeInTheDocument();
    });

    it('shows "No keyword generated" for page without keywords', () => {
      render(<KeywordPageRow page={mockPageWithoutKeywords} projectId={mockProjectId} />);

      expect(screen.getByText('No keyword generated')).toBeInTheDocument();
    });

    it('renders URL with query string', () => {
      const page = createMockPage({
        url: 'https://example.com/search?q=shoes&page=2',
      });
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByText('/search?q=shoes&page=2')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Approve button tests
  // ============================================================================
  describe('approve button', () => {
    it('shows "Approve" button when not approved', () => {
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByRole('button', { name: /Approve/i })).toBeInTheDocument();
    });

    it('shows "Approved" badge when approved', () => {
      const page = createMockPage({
        keywords: {
          ...createMockPage().keywords!,
          is_approved: true,
        },
      });
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByText('Approved')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /^Approve$/i })).not.toBeInTheDocument();
    });

    it('calls approveKeyword mutation when approve button clicked', async () => {
      const user = userEvent.setup();
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      await user.click(screen.getByRole('button', { name: /Approve/i }));

      expect(mockApproveKeyword.mutateAsync).toHaveBeenCalledWith({
        projectId: mockProjectId,
        pageId: 'page-123',
      });
    });

    it('shows loading state during approve', () => {
      mockApproveKeyword.isPending = true;
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByText('Approving...')).toBeInTheDocument();
    });

    it('shows "Pending" when no keyword generated', () => {
      render(<KeywordPageRow page={mockPageWithoutKeywords} projectId={mockProjectId} />);

      expect(screen.getByText('Pending')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Priority toggle tests
  // ============================================================================
  describe('priority toggle', () => {
    it('renders priority star button', () => {
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      const priorityButton = screen.getByRole('button', { name: /priority/i });
      expect(priorityButton).toBeInTheDocument();
    });

    it('shows empty star when not priority', () => {
      const page = createMockPage({
        keywords: {
          ...createMockPage().keywords!,
          is_priority: false,
        },
      });
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      const priorityButton = screen.getByRole('button', { name: /Mark as priority/i });
      expect(priorityButton).toHaveAttribute('aria-pressed', 'false');
    });

    it('shows filled star when priority', () => {
      const page = createMockPage({
        keywords: {
          ...createMockPage().keywords!,
          is_priority: true,
        },
      });
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      const priorityButton = screen.getByRole('button', { name: /Remove priority/i });
      expect(priorityButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('calls togglePriority mutation when star clicked', async () => {
      const user = userEvent.setup();
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      const priorityButton = screen.getByRole('button', { name: /priority/i });
      await user.click(priorityButton);

      expect(mockTogglePriority.mutateAsync).toHaveBeenCalledWith({
        projectId: mockProjectId,
        pageId: 'page-123',
      });
    });

    it('is disabled when no keyword generated', () => {
      render(<KeywordPageRow page={mockPageWithoutKeywords} projectId={mockProjectId} />);

      const priorityButton = screen.getByRole('button', { name: /priority/i });
      expect(priorityButton).toBeDisabled();
    });
  });

  // ============================================================================
  // Score tooltip tests
  // ============================================================================
  describe('score tooltip', () => {
    it('shows score tooltip on hover', async () => {
      const user = userEvent.setup();
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      // Find the score badge by its content
      const scoreBadge = screen.getByText(/52\.3 score/);

      // Hover over the score badge
      await user.hover(scoreBadge);

      // Wait for tooltip to appear
      await waitFor(() => {
        expect(screen.getByText('Score Breakdown')).toBeInTheDocument();
      });
    });

    it('shows weight breakdown in tooltip', async () => {
      const user = userEvent.setup();
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      const scoreBadge = screen.getByText(/52\.3 score/);
      await user.hover(scoreBadge);

      await waitFor(() => {
        expect(screen.getByText('Volume: 50% weight')).toBeInTheDocument();
        expect(screen.getByText('Relevance: 35% weight')).toBeInTheDocument();
        expect(screen.getByText('Competition: 15% weight')).toBeInTheDocument();
      });
    });

    it('hides tooltip on mouse leave', async () => {
      const user = userEvent.setup();
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      const scoreBadge = screen.getByText(/52\.3 score/);

      // Hover to show tooltip
      await user.hover(scoreBadge);
      await waitFor(() => {
        expect(screen.getByText('Score Breakdown')).toBeInTheDocument();
      });

      // Unhover to hide tooltip
      await user.unhover(scoreBadge);
      await waitFor(() => {
        expect(screen.queryByText('Score Breakdown')).not.toBeInTheDocument();
      });
    });

    it('does not show tooltip for null score', () => {
      const page = createMockPage({
        keywords: {
          ...createMockPage().keywords!,
          composite_score: null,
        },
      });
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      // Should show dash but no cursor-help class
      const scoreBadge = screen.getByText(/— score/);
      const parent = scoreBadge.closest('.cursor-help');
      expect(parent).toBeNull();
    });
  });

  // ============================================================================
  // URL tooltip tests
  // ============================================================================
  describe('URL tooltip', () => {
    it('shows full URL on hover', async () => {
      const user = userEvent.setup();
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      const urlDisplay = screen.getByText('/products/running-shoes');
      await user.hover(urlDisplay);

      await waitFor(() => {
        expect(screen.getByText('https://example.com/products/running-shoes')).toBeInTheDocument();
      });
    });
  });

  // ============================================================================
  // Keyword dropdown tests
  // ============================================================================
  describe('keyword dropdown', () => {
    it('opens dropdown when keyword button clicked', async () => {
      const user = userEvent.setup();
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      const keywordButton = screen.getByRole('button', { name: /running shoes/i });
      await user.click(keywordButton);

      await waitFor(() => {
        // Check for alternatives in dropdown
        expect(screen.getByText('best running shoes')).toBeInTheDocument();
        expect(screen.getByText('trail running shoes')).toBeInTheDocument();
      });
    });

    it('has aria-haspopup attribute on keyword button', () => {
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      const keywordButton = screen.getByRole('button', { name: /running shoes/i });
      expect(keywordButton).toHaveAttribute('aria-haspopup', 'listbox');
    });
  });

  // ============================================================================
  // Inline editing tests
  // ============================================================================
  describe('inline editing', () => {
    it('shows Edit button', () => {
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByRole('button', { name: /Edit keyword/i })).toBeInTheDocument();
    });

    it('enters edit mode when Edit button clicked', async () => {
      const user = userEvent.setup();
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      await user.click(screen.getByRole('button', { name: /Edit keyword/i }));

      await waitFor(() => {
        expect(screen.getByRole('textbox', { name: /Edit primary keyword/i })).toBeInTheDocument();
      });
    });

    it('pre-fills input with current keyword', async () => {
      const user = userEvent.setup();
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      await user.click(screen.getByRole('button', { name: /Edit keyword/i }));

      const input = screen.getByRole('textbox', { name: /Edit primary keyword/i });
      expect(input).toHaveValue('running shoes');
    });

    it('saves on Enter key', async () => {
      const user = userEvent.setup();
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      await user.click(screen.getByRole('button', { name: /Edit keyword/i }));
      const input = screen.getByRole('textbox', { name: /Edit primary keyword/i });

      await user.clear(input);
      await user.type(input, 'new keyword{Enter}');

      expect(mockUpdatePrimaryKeyword.mutateAsync).toHaveBeenCalledWith({
        projectId: mockProjectId,
        pageId: 'page-123',
        keyword: 'new keyword',
      });
    });

    it('cancels on Escape key', async () => {
      const user = userEvent.setup();
      const page = createMockPage();
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      await user.click(screen.getByRole('button', { name: /Edit keyword/i }));
      const input = screen.getByRole('textbox', { name: /Edit primary keyword/i });

      await user.clear(input);
      await user.type(input, 'new keyword');
      await user.keyboard('{Escape}');

      // Should exit edit mode without saving
      expect(mockUpdatePrimaryKeyword.mutateAsync).not.toHaveBeenCalled();
      await waitFor(() => {
        expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
      });
    });
  });

  // ============================================================================
  // Edge cases
  // ============================================================================
  describe('edge cases', () => {
    it('handles page without title', () => {
      const page = createMockPage({ title: null });
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.queryByText('Running Shoes Collection')).not.toBeInTheDocument();
      expect(screen.getByText('/products/running-shoes')).toBeInTheDocument();
    });

    it('handles empty title string', () => {
      const page = createMockPage({ title: '' });
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.queryByText('Running Shoes Collection')).not.toBeInTheDocument();
    });

    it('handles invalid URL gracefully', () => {
      const page = createMockPage({ url: 'not-a-valid-url' });
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      // Should display the raw URL
      expect(screen.getByText('not-a-valid-url')).toBeInTheDocument();
    });

    it('handles large search volumes with formatting', () => {
      const page = createMockPage({
        keywords: {
          ...createMockPage().keywords!,
          search_volume: 1500000,
        },
      });
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByText(/1,500,000 vol/)).toBeInTheDocument();
    });

    it('handles zero search volume', () => {
      const page = createMockPage({
        keywords: {
          ...createMockPage().keywords!,
          search_volume: 0,
        },
      });
      render(<KeywordPageRow page={page} projectId={mockProjectId} />);

      expect(screen.getByText(/0 vol/)).toBeInTheDocument();
    });
  });
});
