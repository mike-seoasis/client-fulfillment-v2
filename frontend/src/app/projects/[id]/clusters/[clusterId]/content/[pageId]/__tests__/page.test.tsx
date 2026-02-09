import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ClusterContentEditorPage from '../page';

// ============================================================================
// Mock Next.js navigation
// ============================================================================
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'proj-1', clusterId: 'cluster-1', pageId: 'page-1' }),
  useRouter: () => ({ push: vi.fn() }),
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

vi.mock('@/hooks/useBrandConfig', () => ({
  useBrandConfig: vi.fn(() => ({
    data: null,
    isLoading: false,
  })),
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
    </div>
  ),
}));

vi.mock('@/components/content-editor/HighlightToggleControls', () => ({
  HighlightToggleControls: ({ onChange }: { onChange: (v: { keyword: boolean; lsi: boolean; trope: boolean }) => void }) => (
    <div data-testid="highlight-toggle-controls">
      <button onClick={() => onChange({ keyword: false, lsi: true, trope: true })}>Toggle</button>
    </div>
  ),
  highlightVisibilityClasses: () => '',
}));

vi.mock('@/lib/keyword-variations', () => ({
  generateVariations: () => new Set<string>(),
}));

// ============================================================================
// Mock UI components
// ============================================================================
vi.mock('@/components/ui', () => ({
  Button: ({ children, onClick, disabled, variant, ...rest }: {
    children: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
    variant?: string;
    [key: string]: unknown;
  }) => (
    <button onClick={onClick} disabled={disabled} data-variant={variant} {...rest}>
      {children}
    </button>
  ),
}));

// ============================================================================
// Mock data helpers
// ============================================================================
const createMockContent = (overrides = {}) => ({
  page_title: 'Best Dog Food for Puppies',
  meta_description: 'Find the best dog food options for your growing puppy.',
  top_description: '<p>Introduction paragraph about puppy nutrition.</p>',
  bottom_description: '<h2>Best Brands</h2><p>Content about brands.</p>',
  word_count: 150,
  status: 'complete',
  is_approved: false,
  approved_at: null,
  qa_results: {
    passed: true,
    issues: [],
    checked_at: '2026-02-07T12:00:00Z',
  },
  brief_summary: { keyword: 'best dog food', lsi_terms_count: 3 },
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
  pages_total: 2,
  pages_completed: 2,
  pages_failed: 0,
  pages_approved: 1,
  pages: [
    {
      page_id: 'page-1',
      url: 'https://example.com/puppy-food',
      keyword: 'best dog food',
      status: 'complete',
      error: null,
      qa_passed: true,
      qa_issue_count: 0,
      is_approved: false,
    },
    {
      page_id: 'page-2',
      url: 'https://example.com/cat-food',
      keyword: 'best cat food',
      status: 'complete',
      error: null,
      qa_passed: true,
      qa_issue_count: 0,
      is_approved: true,
    },
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
describe('ClusterContentEditorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  // --------------------------------------------------------------------------
  // "Back to content list" links to cluster path
  // --------------------------------------------------------------------------
  describe('back navigation', () => {
    it('shows "Back to content list" link', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.getByText('Back to content list')).toBeInTheDocument();
    });

    it('"Back to content list" links to cluster content path', () => {
      render(<ClusterContentEditorPage />);
      const link = screen.getByText('Back to content list').closest('a');
      expect(link).toHaveAttribute(
        'href',
        '/projects/proj-1/clusters/cluster-1/content'
      );
    });

    it('"Back to content list" does not link to onboarding path', () => {
      render(<ClusterContentEditorPage />);
      const link = screen.getByText('Back to content list').closest('a');
      expect(link!.getAttribute('href')).not.toContain('/onboarding/');
    });
  });

  // --------------------------------------------------------------------------
  // Error state: "Back to Content" links to cluster path
  // --------------------------------------------------------------------------
  describe('error state navigation', () => {
    it('error state "Back to Content" links to cluster content path', () => {
      mockPageContent.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
      });
      mockContentGenerationStatus.mockReturnValue({ data: undefined });

      render(<ClusterContentEditorPage />);
      const link = screen.getByText('Back to Content').closest('a');
      expect(link).toHaveAttribute(
        'href',
        '/projects/proj-1/clusters/cluster-1/content'
      );
    });

    it('error state does not link to onboarding path', () => {
      mockPageContent.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
      });
      mockContentGenerationStatus.mockReturnValue({ data: undefined });

      render(<ClusterContentEditorPage />);
      const link = screen.getByText('Back to Content').closest('a');
      expect(link!.getAttribute('href')).not.toContain('/onboarding/');
    });
  });

  // --------------------------------------------------------------------------
  // Renders editor with page content
  // --------------------------------------------------------------------------
  describe('renders editor with page content', () => {
    it('renders page title input', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.getByDisplayValue('Best Dog Food for Puppies')).toBeInTheDocument();
    });

    it('renders meta description textarea', () => {
      render(<ClusterContentEditorPage />);
      expect(
        screen.getByDisplayValue(/Find the best dog food options/)
      ).toBeInTheDocument();
    });

    it('renders top description textarea', () => {
      render(<ClusterContentEditorPage />);
      expect(
        screen.getByDisplayValue(/<p>Introduction paragraph about puppy nutrition.<\/p>/)
      ).toBeInTheDocument();
    });

    it('renders bottom description via ContentEditorWithSource', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.getByTestId('content-editor-with-source')).toBeInTheDocument();
    });

    it('renders all 4 field labels', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.getByText('Page Title')).toBeInTheDocument();
      expect(screen.getByText('Meta Description')).toBeInTheDocument();
      expect(screen.getByText('Top Description')).toBeInTheDocument();
      expect(screen.getByText('Bottom Description')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // No onboarding-specific branding
  // --------------------------------------------------------------------------
  describe('no onboarding-specific branding', () => {
    it('does not show "Onboarding" anywhere in the page', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.queryByText(/Onboarding/i)).not.toBeInTheDocument();
    });

    it('does not show step indicator text', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.queryByText(/Step \d/)).not.toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Page info from status endpoint
  // --------------------------------------------------------------------------
  describe('page header', () => {
    it('shows page URL from status endpoint', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.getByText('https://example.com/puppy-food')).toBeInTheDocument();
    });

    it('shows primary keyword badge', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.getByText('best dog food')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Sidebar content
  // --------------------------------------------------------------------------
  describe('sidebar', () => {
    it('renders quality status card', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.getByText('All Checks Passed')).toBeInTheDocument();
    });

    it('renders LSI Terms section', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.getByText('LSI Terms')).toBeInTheDocument();
    });

    it('renders Content Stats section', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.getByText('Content Stats')).toBeInTheDocument();
    });

    it('renders Structure section for heading outline', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.getByText('Structure')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Action bar
  // --------------------------------------------------------------------------
  describe('action bar', () => {
    it('renders Save Draft button', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.getByText('Save Draft')).toBeInTheDocument();
    });

    it('renders Re-run Checks button', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.getByText('Re-run Checks')).toBeInTheDocument();
    });

    it('renders Approve button when not approved', () => {
      render(<ClusterContentEditorPage />);
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    it('renders Approved button when approved', () => {
      setupMocks({ is_approved: true, approved_at: '2026-02-07T12:00:00Z' });
      render(<ClusterContentEditorPage />);
      expect(screen.getByText('Approved')).toBeInTheDocument();
    });
  });
});
