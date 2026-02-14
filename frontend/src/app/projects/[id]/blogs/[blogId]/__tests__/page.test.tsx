import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import BlogKeywordsPage from '../page';

// ============================================================================
// Mock Next.js navigation
// ============================================================================
const mockRouterPush = vi.fn();
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'proj-1', blogId: 'blog-1' }),
  useRouter: () => ({ push: mockRouterPush }),
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>,
}));

// ============================================================================
// Mock UI components
// ============================================================================
vi.mock('@/components/ui', () => ({
  Button: ({ children, onClick, disabled, variant, ref: _ref, ...rest }: any) => (
    <button onClick={onClick} disabled={disabled} data-variant={variant} {...rest}>{children}</button>
  ),
  Toast: ({ message }: { message: string }) => <div data-testid="toast">{message}</div>,
}));

// ============================================================================
// Mock hooks
// ============================================================================
const mockUseProject = vi.fn();
vi.mock('@/hooks/use-projects', () => ({
  useProject: () => mockUseProject(),
}));

const mockUseBlogCampaign = vi.fn();
const mockUpdatePostMutate = vi.fn();
const mockBulkApproveMutate = vi.fn();
const mockDeleteCampaignMutate = vi.fn();
vi.mock('@/hooks/useBlogs', () => ({
  useBlogCampaign: () => mockUseBlogCampaign(),
  useUpdateBlogPost: () => ({
    mutate: mockUpdatePostMutate,
  }),
  useBulkApproveBlogPosts: () => ({
    mutate: mockBulkApproveMutate,
    isPending: false,
  }),
  useDeleteBlogCampaign: () => ({
    mutate: mockDeleteCampaignMutate,
    isPending: false,
  }),
}));

const mockUseCluster = vi.fn();
vi.mock('@/hooks/useClusters', () => ({
  useCluster: () => mockUseCluster(),
}));

// ============================================================================
// Mock data
// ============================================================================
const mockProject = {
  id: 'proj-1',
  name: 'Test Project',
  site_url: 'https://example.com',
};

const mockCampaign = {
  id: 'blog-1',
  project_id: 'proj-1',
  cluster_id: 'cluster-1',
  name: 'Trail Running Blog',
  status: 'planning',
  posts: [
    { id: 'post-1', campaign_id: 'blog-1', primary_keyword: 'best trail shoes', url_slug: 'best-trail-shoes', search_volume: 5000, source_page_id: 'page-1', is_approved: true, content_status: 'pending', content_approved: false, title: null, meta_description: null, content: null, pop_brief: null, qa_results: null, status: 'active', created_at: '2026-01-01', updated_at: '2026-01-01' },
    { id: 'post-2', campaign_id: 'blog-1', primary_keyword: 'trail running tips', url_slug: 'trail-running-tips', search_volume: 3000, source_page_id: null, is_approved: false, content_status: 'pending', content_approved: false, title: null, meta_description: null, content: null, pop_brief: null, qa_results: null, status: 'active', created_at: '2026-01-01', updated_at: '2026-01-01' },
  ],
  generation_metadata: null,
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
};

// ============================================================================
// Default mock return values
// ============================================================================
const defaultMockProject = () => ({
  data: mockProject,
  isLoading: false,
  error: null,
});

const defaultMockCampaign = () => ({
  data: mockCampaign,
  isLoading: false,
  error: null,
});

const defaultMockCluster = () => ({
  data: {
    id: 'cluster-1',
    pages: [
      { id: 'page-1', keyword: 'trail running shoes' },
    ],
  },
  isLoading: false,
  error: null,
});

// ============================================================================
// Tests
// ============================================================================
describe('BlogKeywordsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProject.mockReturnValue(defaultMockProject());
    mockUseBlogCampaign.mockReturnValue(defaultMockCampaign());
    mockUseCluster.mockReturnValue(defaultMockCluster());
  });

  // --------------------------------------------------------------------------
  // Loading state
  // --------------------------------------------------------------------------
  it('shows loading skeleton while data loads', () => {
    mockUseProject.mockReturnValue({ data: undefined, isLoading: true, error: null });
    mockUseBlogCampaign.mockReturnValue({ data: undefined, isLoading: true, error: null });

    render(<BlogKeywordsPage />);

    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Not Found states
  // --------------------------------------------------------------------------
  it('shows "Not Found" when project does not exist', () => {
    mockUseProject.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Not found'),
    });
    mockUseBlogCampaign.mockReturnValue({ data: undefined, isLoading: false, error: null });

    render(<BlogKeywordsPage />);

    expect(screen.getByText('Not Found')).toBeInTheDocument();
  });

  it('shows "Not Found" when campaign does not exist', () => {
    mockUseBlogCampaign.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Not found'),
    });

    render(<BlogKeywordsPage />);

    expect(screen.getByText('Not Found')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Campaign header rendering
  // --------------------------------------------------------------------------
  it('renders campaign name in header', () => {
    render(<BlogKeywordsPage />);

    const headings = screen.getAllByText('Trail Running Blog');
    expect(headings.length).toBeGreaterThan(0);
  });

  // --------------------------------------------------------------------------
  // Blog post rows
  // --------------------------------------------------------------------------
  it('renders blog post rows with keywords and volumes', () => {
    render(<BlogKeywordsPage />);

    // Keywords are rendered via InlineEditableCell as buttons with title "Click to edit"
    expect(screen.getByText('best trail shoes')).toBeInTheDocument();
    expect(screen.getByText('trail running tips')).toBeInTheDocument();

    // Volumes - posts are sorted by search_volume desc so 5000 first, 3000 second
    expect(screen.getByText('5,000')).toBeInTheDocument();
    expect(screen.getByText('3,000')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Approved count stats
  // --------------------------------------------------------------------------
  it('shows approved count stats', () => {
    render(<BlogKeywordsPage />);

    // Summary stats: 2 topics, 1 approved, 1 pending
    expect(screen.getByText('2')).toBeInTheDocument(); // total topics
    expect(screen.getByText('1', { selector: '.text-palm-600' })).toBeInTheDocument(); // approved
    expect(screen.getByText('1', { selector: '.text-lagoon-600' })).toBeInTheDocument(); // pending
  });

  // --------------------------------------------------------------------------
  // Generate Content button enabled when posts are approved
  // --------------------------------------------------------------------------
  it('renders "Generate Content" button that is enabled when posts are approved', () => {
    render(<BlogKeywordsPage />);

    // The button uses &rarr; which renders as the arrow character
    const generateButton = screen.getByRole('button', { name: /Generate Content/ });
    expect(generateButton).not.toBeDisabled();
  });

  // --------------------------------------------------------------------------
  // Approve All
  // --------------------------------------------------------------------------
  it('calls bulkApprove.mutate when "Approve All" is clicked', async () => {
    const user = userEvent.setup();
    render(<BlogKeywordsPage />);

    await user.click(screen.getByRole('button', { name: /Approve All/i }));

    expect(mockBulkApproveMutate).toHaveBeenCalledWith(
      { projectId: 'proj-1', blogId: 'blog-1' },
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      })
    );
  });
});
