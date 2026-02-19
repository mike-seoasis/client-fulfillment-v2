import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ContentEditorPage from '../page';

// ============================================================================
// Mock Next.js navigation
// ============================================================================
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'proj-1', pageId: 'page-1' }),
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// ============================================================================
// Mock hooks
// ============================================================================
const mockPageContent = vi.fn();
const mockContentGenerationStatus = vi.fn();
const mockUpdateContentMutate = vi.fn();
const mockApproveContentMutate = vi.fn();
const mockRecheckContentMutate = vi.fn();

vi.mock('@/hooks/useContentGeneration', () => ({
  usePageContent: () => mockPageContent(),
  useContentGenerationStatus: () => mockContentGenerationStatus(),
  useUpdatePageContent: () => ({
    mutate: mockUpdateContentMutate,
    isPending: false,
  }),
  useApprovePageContent: () => ({
    mutate: mockApproveContentMutate,
    isPending: false,
  }),
  useRecheckPageContent: () => ({
    mutate: mockRecheckContentMutate,
    isPending: false,
  }),
}));

// ============================================================================
// Mock Lexical and content editor components
// ============================================================================
vi.mock('@/components/content-editor/ContentEditorWithSource', () => ({
  ContentEditorWithSource: ({
    initialHtml,
    onChange,
    onBlur,
  }: {
    initialHtml: string;
    onChange?: (html: string) => void;
    onBlur?: () => void;
  }) => (
    <div data-testid="content-editor-with-source">
      <textarea
        data-testid="mock-lexical-editor"
        defaultValue={initialHtml}
        onChange={(e) => onChange?.(e.target.value)}
        onBlur={onBlur}
      />
      <button data-testid="rendered-tab">Rendered</button>
      <button data-testid="html-tab">HTML Source</button>
    </div>
  ),
}));

vi.mock('@/components/content-editor/HighlightToggleControls', () => ({
  HighlightToggleControls: ({ onChange }: { onChange: (v: { keyword: boolean; lsi: boolean; trope: boolean }) => void }) => (
    <div data-testid="highlight-toggle-controls">
      <button onClick={() => onChange({ keyword: false, lsi: true, trope: true })}>Toggle Keywords</button>
    </div>
  ),
  highlightVisibilityClasses: () => '',
}));

vi.mock('@/lib/keyword-variations', () => ({
  generateVariations: () => new Set<string>(),
}));

// ============================================================================
// Mock data helpers
// ============================================================================
const createMockContent = (overrides = {}) => ({
  page_title: 'Best Dog Food for Puppies',
  meta_description: 'Find the best dog food options for your growing puppy. Expert reviews and recommendations.',
  top_description: '<p>Introduction paragraph about puppy nutrition.</p>',
  bottom_description: '<h2>Best Brands</h2><p>Content about brands.</p><h3>Premium Options</h3><p>More content.</p>',
  word_count: 150,
  status: 'complete',
  is_approved: false,
  approved_at: null,
  qa_results: {
    passed: true,
    issues: [],
    checked_at: '2026-02-07T12:00:00Z',
  },
  brief_summary: { keyword: 'best dog food', lsi_terms_count: 5 },
  brief: {
    keyword: 'best dog food',
    lsi_terms: ['puppy nutrition', 'dog kibble', 'wet food'],
    heading_targets: [
      { level: 'h2', min_count: 3, max_count: 8 },
      { level: 'h3', min_count: 4, max_count: 12 },
    ],
    keyword_targets: [],
  },
  generation_started_at: '2026-02-07T11:00:00Z',
  generation_completed_at: '2026-02-07T11:30:00Z',
  ...overrides,
});

const createMockStatus = (overrides = {}) => ({
  overall_status: 'complete',
  pages_total: 5,
  pages_completed: 5,
  pages_failed: 0,
  pages_approved: 2,
  pages: [
    { page_id: 'page-1', url: '/puppy-food', keyword: 'best dog food', status: 'complete', error: null, qa_passed: true, qa_issue_count: 0, is_approved: false },
    { page_id: 'page-2', url: '/cat-food', keyword: 'best cat food', status: 'complete', error: null, qa_passed: true, qa_issue_count: 0, is_approved: true },
  ],
  ...overrides,
});

// ============================================================================
// Default mock setups
// ============================================================================
function setupMocks(contentOverrides = {}, statusOverrides = {}) {
  mockPageContent.mockReturnValue({
    data: createMockContent(contentOverrides),
    isLoading: false,
    isError: false,
  });
  mockContentGenerationStatus.mockReturnValue({
    data: createMockStatus(statusOverrides),
  });
}

// ============================================================================
// Tests
// ============================================================================
describe('ContentEditorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  // --------------------------------------------------------------------------
  // AC: Editor page renders all 4 fields with content from API response
  // --------------------------------------------------------------------------
  describe('renders all 4 fields with content', () => {
    it('renders page title input with correct value', () => {
      render(<ContentEditorPage />);
      const input = screen.getByDisplayValue('Best Dog Food for Puppies');
      expect(input).toBeInTheDocument();
      expect(input.tagName).toBe('INPUT');
    });

    it('renders meta description textarea with correct value', () => {
      render(<ContentEditorPage />);
      const textarea = screen.getByDisplayValue(/Find the best dog food options/);
      expect(textarea).toBeInTheDocument();
      expect(textarea.tagName).toBe('TEXTAREA');
    });

    it('renders top description textarea with correct value', () => {
      render(<ContentEditorPage />);
      // Top description contains HTML — the textarea will display the raw HTML
      const textarea = screen.getByDisplayValue(/<p>Introduction paragraph about puppy nutrition.<\/p>/);
      expect(textarea).toBeInTheDocument();
    });

    it('renders bottom description via ContentEditorWithSource', () => {
      render(<ContentEditorPage />);
      expect(screen.getByTestId('content-editor-with-source')).toBeInTheDocument();
      // The mock editor receives the initial HTML
      const editor = screen.getByTestId('mock-lexical-editor');
      expect(editor).toHaveValue('<h2>Best Brands</h2><p>Content about brands.</p><h3>Premium Options</h3><p>More content.</p>');
    });

    it('renders all 4 field labels', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('Page Title')).toBeInTheDocument();
      expect(screen.getByText('Meta Description')).toBeInTheDocument();
      expect(screen.getByText('Top Description')).toBeInTheDocument();
      expect(screen.getByText('Bottom Description')).toBeInTheDocument();
    });

    it('shows loading skeleton when data is loading', () => {
      mockPageContent.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
      });
      mockContentGenerationStatus.mockReturnValue({ data: undefined });

      render(<ContentEditorPage />);
      // Loading state should show placeholder divs (animate-pulse)
      expect(screen.queryByText('Page Title')).not.toBeInTheDocument();
    });

    it('shows error state when data fails to load', () => {
      mockPageContent.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
      });
      mockContentGenerationStatus.mockReturnValue({ data: undefined });

      render(<ContentEditorPage />);
      expect(screen.getByText('Failed to load content for this page.')).toBeInTheDocument();
      expect(screen.getByText('Back to Content')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // AC: Character counters update on input and change color when over limit
  // --------------------------------------------------------------------------
  describe('character counters', () => {
    it('shows page title character counter with correct value', () => {
      render(<ContentEditorPage />);
      // "Best Dog Food for Puppies" is 25 chars
      expect(screen.getByText('25 / 70')).toBeInTheDocument();
    });

    it('shows meta description character counter with correct value', () => {
      render(<ContentEditorPage />);
      // "Find the best dog food options for your growing puppy. Expert reviews and recommendations." is 90 chars
      expect(screen.getByText('90 / 160')).toBeInTheDocument();
    });

    it('shows counter in palm color when under limit', () => {
      render(<ContentEditorPage />);
      // Title counter (25 / 70) should be palm (green)
      const counter = screen.getByText('25 / 70');
      expect(counter).toHaveClass('text-palm-600');
    });

    it('shows counter in coral color when over limit', () => {
      setupMocks({
        page_title: 'A'.repeat(75), // Over 70 char limit
      });
      render(<ContentEditorPage />);
      const counter = screen.getByText('75 / 70');
      expect(counter).toHaveClass('text-coral-600');
    });

    it('updates title character counter on input', async () => {
      const user = userEvent.setup();
      render(<ContentEditorPage />);

      const input = screen.getByDisplayValue('Best Dog Food for Puppies');
      await user.clear(input);
      await user.type(input, 'New Title');
      expect(screen.getByText('9 / 70')).toBeInTheDocument();
    });

    it('updates meta description character counter on input', async () => {
      const user = userEvent.setup();
      render(<ContentEditorPage />);

      const textarea = screen.getByDisplayValue(/Find the best dog food options/);
      await user.clear(textarea);
      await user.type(textarea, 'Short meta');
      expect(screen.getByText('10 / 160')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // AC: Sidebar renders quality check results correctly (pass and fail states)
  // --------------------------------------------------------------------------
  describe('sidebar quality checks', () => {
    it('renders quality status card with "All Checks Passed" when passed', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('All Checks Passed')).toBeInTheDocument();
    });

    it('shows "Pass" for each check type when no issues', () => {
      render(<ContentEditorPage />);
      const passElements = screen.getAllByText('Pass');
      expect(passElements.length).toBe(8); // 8 check types
    });

    it('renders quality status card with issue count when failed', () => {
      setupMocks({
        qa_results: {
          passed: false,
          issues: [
            { type: 'ai_pattern', field: 'bottom_description', description: 'AI opener detected', context: 'In the world of' },
            { type: 'ai_pattern', field: 'bottom_description', description: 'AI opener detected', context: 'When it comes to' },
            { type: 'em_dash', field: 'bottom_description', description: 'Em dash usage', context: 'food — and' },
          ],
          checked_at: '2026-02-07T12:00:00Z',
        },
      });
      render(<ContentEditorPage />);
      expect(screen.getByText('3 Issues Found')).toBeInTheDocument();
    });

    it('shows correct issue count per check type when issues exist', () => {
      setupMocks({
        qa_results: {
          passed: false,
          issues: [
            { type: 'ai_pattern', field: 'bottom_description', description: 'AI opener', context: 'In the world of' },
            { type: 'ai_pattern', field: 'bottom_description', description: 'AI opener', context: 'When it comes to' },
            { type: 'em_dash', field: 'bottom_description', description: 'Em dash', context: 'food — and' },
          ],
          checked_at: '2026-02-07T12:00:00Z',
        },
      });
      render(<ContentEditorPage />);
      // ai_pattern should show "2 found"
      expect(screen.getByText('2 found')).toBeInTheDocument();
      // em_dash should show "1 found"
      expect(screen.getByText('1 found')).toBeInTheDocument();
      // Other types should show "Pass" (6 remaining)
      const passElements = screen.getAllByText('Pass');
      expect(passElements.length).toBe(6);
    });

    it('displays all check type labels', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('Banned Words')).toBeInTheDocument();
      expect(screen.getByText('Em Dashes')).toBeInTheDocument();
      expect(screen.getByText('AI Openers')).toBeInTheDocument();
      expect(screen.getByText('Triplet Lists')).toBeInTheDocument();
      expect(screen.getByText('Rhetorical Questions')).toBeInTheDocument();
      expect(screen.getByText('Tier 1 AI Words')).toBeInTheDocument();
      expect(screen.getByText('Tier 2 AI Words')).toBeInTheDocument();
      expect(screen.getByText('Negation Contrast')).toBeInTheDocument();
    });

    it('does not render quality card when qa_results is null', () => {
      setupMocks({ qa_results: null });
      render(<ContentEditorPage />);
      expect(screen.queryByText('All Checks Passed')).not.toBeInTheDocument();
      expect(screen.queryByText('Banned Words')).not.toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // AC: Flagged passages card
  // --------------------------------------------------------------------------
  describe('flagged passages', () => {
    it('renders flagged passages when issues exist', () => {
      setupMocks({
        qa_results: {
          passed: false,
          issues: [
            { type: 'ai_pattern', field: 'bottom_description', description: 'AI opener detected', context: 'In the world of dogs' },
          ],
          checked_at: '2026-02-07T12:00:00Z',
        },
      });
      render(<ContentEditorPage />);
      expect(screen.getByText('Flagged Passages')).toBeInTheDocument();
      expect(screen.getByText('AI opener detected')).toBeInTheDocument();
    });

    it('does not render flagged passages card when no issues', () => {
      render(<ContentEditorPage />);
      expect(screen.queryByText('Flagged Passages')).not.toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // AC: LSI term checklist shows found vs missing terms
  // --------------------------------------------------------------------------
  describe('LSI terms checklist', () => {
    it('renders LSI Terms heading', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('LSI Terms')).toBeInTheDocument();
    });

    it('renders all LSI terms from brief', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('puppy nutrition')).toBeInTheDocument();
      expect(screen.getByText('dog kibble')).toBeInTheDocument();
      expect(screen.getByText('wet food')).toBeInTheDocument();
    });

    it('shows "not found" for terms not in bottom description', () => {
      render(<ContentEditorPage />);
      // Bottom description does not contain any of the LSI terms
      const notFoundLabels = screen.getAllByText('not found');
      expect(notFoundLabels.length).toBe(3);
    });

    it('shows found terms with count when terms appear in content', () => {
      setupMocks({
        bottom_description: '<p>puppy nutrition is important. puppy nutrition guide.</p>',
        brief: {
          keyword: 'best dog food',
          lsi_terms: ['puppy nutrition', 'dog kibble'],
          heading_targets: [],
          keyword_targets: [],
        },
      });
      render(<ContentEditorPage />);
      // "puppy nutrition" should be found, "dog kibble" should not
      expect(screen.getByText('not found')).toBeInTheDocument();
      // Should show summary "1 of 2 terms used"
      expect(screen.getByText('1 of 2 terms used')).toBeInTheDocument();
    });

    it('shows summary count of terms used', () => {
      render(<ContentEditorPage />);
      // 0 of 3 found
      expect(screen.getByText('0 of 3 terms used')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // AC: Approval button toggles state
  // --------------------------------------------------------------------------
  describe('approval button', () => {
    it('shows "Approve" button when content is not approved', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    it('shows "Approved" button when content is approved', () => {
      setupMocks({ is_approved: true, approved_at: '2026-02-07T12:00:00Z' });
      render(<ContentEditorPage />);
      expect(screen.getByText('Approved')).toBeInTheDocument();
    });

    it('calls approveContent mutation with value=true when unapproved', async () => {
      const user = userEvent.setup();
      render(<ContentEditorPage />);

      await user.click(screen.getByText('Approve'));
      expect(mockApproveContentMutate).toHaveBeenCalledWith({
        projectId: 'proj-1',
        pageId: 'page-1',
        value: true,
      });
    });

    it('calls approveContent mutation with value=false when approved', async () => {
      const user = userEvent.setup();
      setupMocks({ is_approved: true, approved_at: '2026-02-07T12:00:00Z' });
      render(<ContentEditorPage />);

      await user.click(screen.getByText('Approved'));
      expect(mockApproveContentMutate).toHaveBeenCalledWith({
        projectId: 'proj-1',
        pageId: 'page-1',
        value: false,
      });
    });

    it('disables approve button when content status is not complete', () => {
      setupMocks({ status: 'generating' });
      render(<ContentEditorPage />);

      const approveBtn = screen.getByText('Approve').closest('button')!;
      expect(approveBtn).toBeDisabled();
    });

    it('approved button has palm-tinted styling when approved', () => {
      setupMocks({ is_approved: true, approved_at: '2026-02-07T12:00:00Z' });
      render(<ContentEditorPage />);

      const approveBtn = screen.getByText('Approved').closest('button')!;
      expect(approveBtn).toHaveClass('bg-palm-100');
    });
  });

  // --------------------------------------------------------------------------
  // Rendered/HTML tab switching (delegated to ContentEditorWithSource mock)
  // --------------------------------------------------------------------------
  describe('rendered/HTML tab switching', () => {
    it('renders both tab buttons via ContentEditorWithSource', () => {
      render(<ContentEditorPage />);
      expect(screen.getByTestId('rendered-tab')).toBeInTheDocument();
      expect(screen.getByTestId('html-tab')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Header and page info
  // --------------------------------------------------------------------------
  describe('header', () => {
    it('shows page URL from status endpoint', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('/puppy-food')).toBeInTheDocument();
    });

    it('shows primary keyword badge', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('best dog food')).toBeInTheDocument();
    });

    it('shows back to content list link', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('Back to content list')).toBeInTheDocument();
    });

    it('shows highlight toggle controls', () => {
      render(<ContentEditorPage />);
      expect(screen.getByTestId('highlight-toggle-controls')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Bottom action bar
  // --------------------------------------------------------------------------
  describe('bottom action bar', () => {
    it('renders Save Draft button', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('Save Draft')).toBeInTheDocument();
    });

    it('renders Re-run Checks button', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('Re-run Checks')).toBeInTheDocument();
    });

    it('triggers save when Save Draft is clicked', async () => {
      const user = userEvent.setup();
      render(<ContentEditorPage />);

      await user.click(screen.getByText('Save Draft'));
      expect(mockUpdateContentMutate).toHaveBeenCalled();
    });

    it('triggers save + recheck when Re-run Checks is clicked', async () => {
      const user = userEvent.setup();
      render(<ContentEditorPage />);

      await user.click(screen.getByText('Re-run Checks'));
      // Should call updateContent first (save before recheck)
      expect(mockUpdateContentMutate).toHaveBeenCalled();
    });
  });

  // --------------------------------------------------------------------------
  // Content stats card
  // --------------------------------------------------------------------------
  describe('content stats', () => {
    it('renders Content Stats heading', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('Content Stats')).toBeInTheDocument();
    });

    it('renders word count in stats', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('Word Count')).toBeInTheDocument();
    });

    it('renders heading counts in stats', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('Headings')).toBeInTheDocument();
    });

    it('renders heading targets from brief', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('Target: 3\u20138 H2, 4\u201312 H3')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Heading outline card
  // --------------------------------------------------------------------------
  describe('heading outline', () => {
    it('renders Structure heading', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('Structure')).toBeInTheDocument();
    });

    it('renders H2 and H3 headings from bottom description', () => {
      render(<ContentEditorPage />);
      expect(screen.getByText('H2 — Best Brands')).toBeInTheDocument();
      expect(screen.getByText('H3 — Premium Options')).toBeInTheDocument();
    });

    it('heading items are keyboard accessible', () => {
      render(<ContentEditorPage />);
      const h2Item = screen.getByText('H2 — Best Brands');
      expect(h2Item.closest('[role="button"]')).toBeInTheDocument();
      expect(h2Item.closest('[tabindex="0"]')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Word count footer for bottom description
  // --------------------------------------------------------------------------
  describe('bottom description footer', () => {
    it('shows word count for bottom description', () => {
      render(<ContentEditorPage />);
      // The footer shows "N words" — there are multiple elements with "words" text
      const wordCountEls = screen.getAllByText(/\d+ words$/);
      expect(wordCountEls.length).toBeGreaterThanOrEqual(1);
    });

    it('shows heading counts in footer', () => {
      render(<ContentEditorPage />);
      // Bottom description has 1 H2 and 1 H3
      const h2Els = screen.getAllByText('1 H2');
      expect(h2Els.length).toBeGreaterThanOrEqual(1);
      const h3Els = screen.getAllByText('1 H3');
      expect(h3Els.length).toBeGreaterThanOrEqual(1);
    });
  });
});
