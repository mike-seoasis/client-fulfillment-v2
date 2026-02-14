import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import BlogContentPage from '../page';

// ============================================================================
// Mock Next.js navigation
// ============================================================================
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'proj-1', blogId: 'blog-1' }),
  useRouter: () => ({ push: vi.fn() }),
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
const mockUseBlogContentStatus = vi.fn();
const mockTriggerMutateAsync = vi.fn();
const mockBulkApproveContentMutateAsync = vi.fn();
const mockApprovePostContentMutate = vi.fn();

vi.mock('@/hooks/useBlogs', () => ({
  useBlogCampaign: () => mockUseBlogCampaign(),
  useBlogContentStatus: () => mockUseBlogContentStatus(),
  useTriggerBlogContentGeneration: () => ({
    mutateAsync: mockTriggerMutateAsync,
    isPending: false,
  }),
  useBulkApproveBlogContent: () => ({
    mutateAsync: mockBulkApproveContentMutateAsync,
    isPending: false,
  }),
  useApproveBlogPostContent: () => ({
    mutate: mockApprovePostContentMutate,
    isPending: false,
  }),
}));

// ============================================================================
// Mock data
// ============================================================================
const mockProject = {
  id: 'proj-1',
  name: 'Test Project',
  site_url: 'https://example.com',
};

const basePost = {
  campaign_id: 'blog-1',
  url_slug: 'test-slug',
  search_volume: 1000,
  source_page_id: null,
  title: null,
  meta_description: null,
  pop_brief: null,
  status: 'active',
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
};

const mockCampaign = {
  id: 'blog-1',
  project_id: 'proj-1',
  cluster_id: 'cluster-1',
  name: 'Trail Running Blog',
  status: 'planning',
  posts: [
    { ...basePost, id: 'post-1', primary_keyword: 'best trail shoes', is_approved: true, content_status: 'pending', content_approved: false, content: null, qa_results: null },
    { ...basePost, id: 'post-2', primary_keyword: 'trail running tips', is_approved: false, content_status: 'pending', content_approved: false, content: null, qa_results: null },
  ],
  generation_metadata: null,
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
};

const mockCampaignWithContent = {
  ...mockCampaign,
  posts: [
    { ...basePost, id: 'post-1', primary_keyword: 'best trail shoes', is_approved: true, content_status: 'complete', content_approved: false, content: '<p>This is a test blog post about trail shoes with enough words.</p>', qa_results: { passed: true, issues: [] } },
    { ...basePost, id: 'post-2', primary_keyword: 'trail running tips', is_approved: true, content_status: 'complete', content_approved: true, content: '<p>Tips for trail running.</p>', qa_results: { passed: false, issues: [{ type: 'ai_pattern', field: 'content', description: 'AI opener', context: 'test context' }] } },
  ],
};

const mockContentStatusIdle = {
  overall_status: 'idle',
  posts_total: 0,
  posts_completed: 0,
  posts_failed: 0,
  posts: [],
};

const mockContentStatusGenerating = {
  overall_status: 'generating',
  posts_total: 2,
  posts_completed: 1,
  posts_failed: 0,
  posts: [
    { post_id: 'post-1', primary_keyword: 'best trail shoes', content_status: 'complete' },
    { post_id: 'post-2', primary_keyword: 'trail running tips', content_status: 'writing' },
  ],
};

const mockContentStatusComplete = {
  overall_status: 'complete',
  posts_total: 2,
  posts_completed: 2,
  posts_failed: 0,
  posts: [
    { post_id: 'post-1', primary_keyword: 'best trail shoes', content_status: 'complete' },
    { post_id: 'post-2', primary_keyword: 'trail running tips', content_status: 'complete' },
  ],
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

const defaultMockContentStatus = () => ({
  data: mockContentStatusIdle,
  isLoading: false,
  error: null,
});

// ============================================================================
// Tests
// ============================================================================
describe('BlogContentPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProject.mockReturnValue(defaultMockProject());
    mockUseBlogCampaign.mockReturnValue(defaultMockCampaign());
    mockUseBlogContentStatus.mockReturnValue(defaultMockContentStatus());
  });

  // --------------------------------------------------------------------------
  // Loading state
  // --------------------------------------------------------------------------
  it('shows loading skeleton while data loads', () => {
    mockUseProject.mockReturnValue({ data: undefined, isLoading: true, error: null });
    mockUseBlogCampaign.mockReturnValue({ data: undefined, isLoading: true, error: null });
    mockUseBlogContentStatus.mockReturnValue({ data: undefined, isLoading: true, error: null });

    render(<BlogContentPage />);

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
    mockUseBlogContentStatus.mockReturnValue({ data: undefined, isLoading: false, error: null });

    render(<BlogContentPage />);

    expect(screen.getByText('Not Found')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Generate Content button when idle with approved posts
  // --------------------------------------------------------------------------
  it('shows "Generate Content" button when idle and has approved posts', () => {
    // Campaign has post-1 approved, content status is idle
    mockUseBlogContentStatus.mockReturnValue({
      data: mockContentStatusIdle,
      isLoading: false,
      error: null,
    });

    render(<BlogContentPage />);

    expect(screen.getByRole('button', { name: /Generate Content/i })).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // No Approved Topics message when idle and no approved posts
  // --------------------------------------------------------------------------
  it('shows "No Approved Topics" message when idle and no approved posts', () => {
    const noneApproved = {
      ...mockCampaign,
      posts: mockCampaign.posts.map((p) => ({ ...p, is_approved: false })),
    };
    mockUseBlogCampaign.mockReturnValue({
      data: noneApproved,
      isLoading: false,
      error: null,
    });
    mockUseBlogContentStatus.mockReturnValue({
      data: mockContentStatusIdle,
      isLoading: false,
      error: null,
    });

    render(<BlogContentPage />);

    expect(screen.getByText('No Approved Topics')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Progress bar during generation
  // --------------------------------------------------------------------------
  it('shows progress bar during generation', () => {
    mockUseBlogCampaign.mockReturnValue({
      data: mockCampaignWithContent,
      isLoading: false,
      error: null,
    });
    mockUseBlogContentStatus.mockReturnValue({
      data: mockContentStatusGenerating,
      isLoading: false,
      error: null,
    });

    render(<BlogContentPage />);

    // Progress text: "1 of 2 complete"
    expect(screen.getByText(/1 of 2 complete/)).toBeInTheDocument();
    // Progress percentage
    expect(screen.getByText('50%')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Review table with "Needs Review" tab after generation completes
  // --------------------------------------------------------------------------
  it('shows review table with "Needs Review" tab after generation completes', () => {
    mockUseBlogCampaign.mockReturnValue({
      data: mockCampaignWithContent,
      isLoading: false,
      error: null,
    });
    mockUseBlogContentStatus.mockReturnValue({
      data: mockContentStatusComplete,
      isLoading: false,
      error: null,
    });

    render(<BlogContentPage />);

    expect(screen.getByText('Needs Review')).toBeInTheDocument();
    expect(screen.getByText('Approved')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Post keywords in review table
  // --------------------------------------------------------------------------
  it('shows post keywords in review table', () => {
    mockUseBlogCampaign.mockReturnValue({
      data: mockCampaignWithContent,
      isLoading: false,
      error: null,
    });
    mockUseBlogContentStatus.mockReturnValue({
      data: mockContentStatusComplete,
      isLoading: false,
      error: null,
    });

    render(<BlogContentPage />);

    // Post-1 is content_approved: false, so it shows on the "Needs Review" tab by default
    expect(screen.getByText('best trail shoes')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Tab switching: clicking "Approved" tab shows approved posts
  // --------------------------------------------------------------------------
  it('shows approved posts when clicking the "Approved" tab', async () => {
    const user = userEvent.setup();

    mockUseBlogCampaign.mockReturnValue({
      data: mockCampaignWithContent,
      isLoading: false,
      error: null,
    });
    mockUseBlogContentStatus.mockReturnValue({
      data: mockContentStatusComplete,
      isLoading: false,
      error: null,
    });

    render(<BlogContentPage />);

    // Click the "Approved" tab
    const approvedTab = screen.getByRole('button', { name: /Approved/i });
    await user.click(approvedTab);

    // Post-2 has content_approved: true, so it should appear in the Approved tab
    expect(screen.getByText('trail running tips')).toBeInTheDocument();
  });
});
