import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import BlogExportPage from '../page';

// ============================================================================
// Mock Next.js navigation
// ============================================================================
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'proj-1', blogId: 'blog-1' }),
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// ============================================================================
// Mock hooks
// ============================================================================
const mockUseProject = vi.fn();
vi.mock('@/hooks/use-projects', () => ({
  useProject: () => mockUseProject(),
}));

const mockUseBlogCampaign = vi.fn();
const mockUseBlogExport = vi.fn();
const mockDownloadMutate = vi.fn();

vi.mock('@/hooks/useBlogs', () => ({
  useBlogCampaign: () => mockUseBlogCampaign(),
  useBlogExport: () => mockUseBlogExport(),
  useDownloadBlogPostHtml: () => ({
    mutate: mockDownloadMutate,
    isPending: false,
  }),
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
  Toast: ({
    message,
    onClose,
  }: {
    message: string;
    variant?: string;
    onClose: () => void;
  }) => (
    <div data-testid="toast" onClick={onClose}>
      {message}
    </div>
  ),
}));

// ============================================================================
// Mock data
// ============================================================================
const mockProject = {
  id: 'proj-1',
  name: 'Test Project',
  site_url: 'https://example.com',
};

const mockExportItems = [
  {
    post_id: 'post-1',
    primary_keyword: 'best trail shoes',
    url_slug: 'best-trail-shoes',
    title: 'Best Trail Shoes 2026',
    meta_description: 'Find the best trail shoes.',
    html_content: '<p>Content here</p>',
    word_count: 250,
  },
  {
    post_id: 'post-2',
    primary_keyword: 'trail running tips',
    url_slug: 'trail-running-tips',
    title: 'Trail Running Tips',
    meta_description: 'Tips for trail running.',
    html_content: '<p>More content</p>',
    word_count: 180,
  },
];

const mockCampaign = {
  id: 'blog-1',
  project_id: 'proj-1',
  cluster_id: 'cluster-1',
  name: 'Trail Running Blog',
  status: 'complete',
  posts: [
    {
      id: 'post-1',
      primary_keyword: 'best trail shoes',
      url_slug: 'best-trail-shoes',
      is_approved: true,
      content_status: 'complete',
      content_approved: true,
    },
    {
      id: 'post-2',
      primary_keyword: 'trail running tips',
      url_slug: 'trail-running-tips',
      is_approved: true,
      content_status: 'complete',
      content_approved: true,
    },
    {
      id: 'post-3',
      primary_keyword: 'trail gear guide',
      url_slug: 'trail-gear-guide',
      is_approved: false,
      content_status: 'pending',
      content_approved: false,
    },
  ],
};

// ============================================================================
// Default mock setups
// ============================================================================
function setupMocks() {
  mockUseProject.mockReturnValue({
    data: mockProject,
    isLoading: false,
  });
  mockUseBlogCampaign.mockReturnValue({
    data: mockCampaign,
    isLoading: false,
  });
  mockUseBlogExport.mockReturnValue({
    data: mockExportItems,
    isLoading: false,
  });
}

// ============================================================================
// Tests
// ============================================================================
describe('BlogExportPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  // --------------------------------------------------------------------------
  // Loading state
  // --------------------------------------------------------------------------
  it('shows loading skeleton while data loads', () => {
    mockUseProject.mockReturnValue({ data: undefined, isLoading: true });
    mockUseBlogCampaign.mockReturnValue({ data: undefined, isLoading: true });
    mockUseBlogExport.mockReturnValue({ data: undefined, isLoading: true });

    render(<BlogExportPage />);

    expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Not found state
  // --------------------------------------------------------------------------
  it('shows "Not Found" when project does not exist', () => {
    mockUseProject.mockReturnValue({ data: undefined, isLoading: false });
    mockUseBlogCampaign.mockReturnValue({ data: mockCampaign, isLoading: false });
    mockUseBlogExport.mockReturnValue({ data: mockExportItems, isLoading: false });

    render(<BlogExportPage />);

    expect(screen.getByText('Not Found')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Export heading
  // --------------------------------------------------------------------------
  it('renders "Export Blog Posts" heading', () => {
    render(<BlogExportPage />);

    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading).toHaveTextContent('Export Blog Posts');
  });

  // --------------------------------------------------------------------------
  // Ready count badge
  // --------------------------------------------------------------------------
  it('shows ready count badge ("Ready to export: 2 of 3 posts approved")', () => {
    render(<BlogExportPage />);

    expect(
      screen.getByText('Ready to export: 2 of 3 posts approved')
    ).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Export post cards with keywords and word counts
  // --------------------------------------------------------------------------
  it('renders export post cards with keywords and word counts', () => {
    render(<BlogExportPage />);

    expect(screen.getByText('best trail shoes')).toBeInTheDocument();
    expect(screen.getByText('trail running tips')).toBeInTheDocument();
    expect(screen.getByText('250 words')).toBeInTheDocument();
    expect(screen.getByText('180 words')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Unapproved posts grayed out
  // --------------------------------------------------------------------------
  it('shows unapproved posts in grayed-out section', () => {
    render(<BlogExportPage />);

    expect(screen.getByText('Unapproved (1)')).toBeInTheDocument();
    expect(screen.getByText('trail gear guide')).toBeInTheDocument();
    expect(screen.getByText('Not approved')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Copy HTML button
  // --------------------------------------------------------------------------
  it('Copy HTML button calls navigator.clipboard.writeText', async () => {
    render(<BlogExportPage />);

    const copyButtons = screen.getAllByText('Copy HTML');
    await act(async () => {
      fireEvent.click(copyButtons[0]);
    });

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      '<p>Content here</p>'
    );
  });

  // --------------------------------------------------------------------------
  // Copy All HTML button
  // --------------------------------------------------------------------------
  it('Copy All HTML button copies combined content with separators', async () => {
    render(<BlogExportPage />);

    const copyAllButton = screen.getByText('Copy All HTML');
    await act(async () => {
      fireEvent.click(copyAllButton);
    });

    const expectedCombined =
      '<!-- POST: best trail shoes -->\n<p>Content here</p>\n\n<!-- POST: trail running tips -->\n<p>More content</p>';
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expectedCombined);
  });
});
