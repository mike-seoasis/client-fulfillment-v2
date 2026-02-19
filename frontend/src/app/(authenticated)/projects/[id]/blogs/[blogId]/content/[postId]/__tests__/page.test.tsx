import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import BlogContentEditorPage from '../page';

// ============================================================================
// Mock Next.js navigation
// ============================================================================
const mockRouterPush = vi.fn();
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'proj-1', blogId: 'blog-1', postId: 'post-1' }),
  useRouter: () => ({ push: mockRouterPush }),
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// ============================================================================
// Mock hooks
// ============================================================================
const mockBlogPostContent = vi.fn();
const mockUpdateContentMutate = vi.fn();
const mockApproveContentMutate = vi.fn();
const mockRecheckContentMutate = vi.fn();

vi.mock('@/hooks/useBlogs', () => ({
  useBlogPostContent: () => mockBlogPostContent(),
  useUpdateBlogPostContent: () => ({
    mutate: mockUpdateContentMutate,
    isPending: false,
  }),
  useApproveBlogPostContent: () => ({
    mutate: mockApproveContentMutate,
    isPending: false,
  }),
  useRecheckBlogPostContent: () => ({
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
    <div data-testid="content-editor">
      <textarea
        data-testid="mock-editor"
        defaultValue={initialHtml}
        onChange={(e) => onChange?.(e.target.value)}
        onBlur={onBlur}
      />
    </div>
  ),
}));

vi.mock('@/components/content-editor/HighlightToggleControls', () => ({
  HighlightToggleControls: () => <div data-testid="highlight-controls" />,
  highlightVisibilityClasses: () => '',
}));

vi.mock('@/lib/keyword-variations', () => ({
  generateVariations: () => new Set(['trail shoes', 'running shoes']),
}));

// ============================================================================
// Mock UI components
// ============================================================================
vi.mock('@/components/ui', () => ({
  Button: ({
    children,
    onClick,
    disabled,
    variant,
    ...rest
  }: {
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
const mockPost = {
  id: 'post-1',
  campaign_id: 'blog-1',
  primary_keyword: 'best trail shoes',
  url_slug: 'best-trail-shoes',
  search_volume: 5000,
  source_page_id: null,
  is_approved: true,
  content_status: 'complete',
  content_approved: false,
  title: 'Best Trail Running Shoes for 2026',
  meta_description: 'Find the best trail running shoes for your next adventure.',
  content: '<h2>Top Trail Shoes</h2><p>Here are some great options.</p>',
  pop_brief: {
    lsi_terms: ['hiking', 'terrain'],
    heading_targets: [{ level: 'h2', min_count: 3, max_count: 5 }],
  },
  qa_results: { passed: true, issues: [] },
  status: 'active',
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
};

// ============================================================================
// Default mock setups
// ============================================================================
function setupMocks(overrides = {}) {
  mockBlogPostContent.mockReturnValue({
    data: { ...mockPost, ...overrides },
    isLoading: false,
    isError: false,
  });
}

// ============================================================================
// Tests
// ============================================================================
describe('BlogContentEditorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  // --------------------------------------------------------------------------
  // Loading state
  // --------------------------------------------------------------------------
  it('shows loading skeleton while data loads', () => {
    mockBlogPostContent.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });

    render(<BlogContentEditorPage />);

    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Error state
  // --------------------------------------------------------------------------
  it('shows error state when post load fails', () => {
    mockBlogPostContent.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    render(<BlogContentEditorPage />);

    expect(
      screen.getByText('Failed to load content for this blog post.')
    ).toBeInTheDocument();
    const link = screen.getByText('Back to Content').closest('a');
    expect(link).toHaveAttribute(
      'href',
      '/projects/proj-1/blogs/blog-1/content'
    );
  });

  // --------------------------------------------------------------------------
  // 3-field editor layout
  // --------------------------------------------------------------------------
  it('renders 3-field editor layout (Page Title, Meta Description, Content)', () => {
    render(<BlogContentEditorPage />);

    expect(screen.getByText('Page Title')).toBeInTheDocument();
    expect(screen.getByText('Meta Description')).toBeInTheDocument();
    expect(screen.getByText('Content')).toBeInTheDocument();
    expect(screen.getByTestId('content-editor')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Primary keyword heading
  // --------------------------------------------------------------------------
  it('displays the post primary keyword as page heading', () => {
    render(<BlogContentEditorPage />);

    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading).toHaveTextContent('best trail shoes');
  });

  // --------------------------------------------------------------------------
  // Character counter for title
  // --------------------------------------------------------------------------
  it('displays character counter for title field (shows "X / 70")', () => {
    render(<BlogContentEditorPage />);

    // Title is "Best Trail Running Shoes for 2026" = 35 chars
    const titleLen = mockPost.title.length;
    expect(screen.getByText(`${titleLen} / 70`)).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Character counter for meta description
  // --------------------------------------------------------------------------
  it('displays character counter for meta description field (shows "X / 160")', () => {
    render(<BlogContentEditorPage />);

    // Meta description is "Find the best trail running shoes for your next adventure." = 58 chars
    const metaLen = mockPost.meta_description.length;
    expect(screen.getByText(`${metaLen} / 160`)).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Approve button for unapproved posts
  // --------------------------------------------------------------------------
  it('shows "Approve" button for unapproved posts', () => {
    setupMocks({ content_approved: false });

    render(<BlogContentEditorPage />);

    expect(screen.getByText('Approve')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Approved button for approved posts
  // --------------------------------------------------------------------------
  it('shows "Approved" button text for approved posts', () => {
    setupMocks({ content_approved: true });

    render(<BlogContentEditorPage />);

    expect(screen.getByText('Approved')).toBeInTheDocument();
  });
});
