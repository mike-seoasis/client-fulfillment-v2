import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import NewBlogCampaignPage from '../page';
import type { ClusterListItem, BlogCampaignListItem } from '@/lib/api';

// ============================================================================
// Mock Next.js navigation
// ============================================================================
const mockRouterPush = vi.fn();
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'proj-1' }),
  useRouter: () => ({ push: mockRouterPush }),
}));

// ============================================================================
// Mock next/link
// ============================================================================
vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// ============================================================================
// Mock UI components
// ============================================================================
vi.mock('@/components/ui', () => ({
  Button: ({ children, onClick, disabled, variant, ...rest }: any) => (
    <button
      onClick={onClick}
      aria-disabled={disabled || undefined}
      data-variant={variant}
      {...rest}
    >
      {children}
    </button>
  ),
  Input: ({ label, value, onChange, placeholder, ...rest }: any) => (
    <div>
      {label && <label>{label}</label>}
      <input value={value} onChange={onChange} placeholder={placeholder} {...rest} />
    </div>
  ),
}));

// ============================================================================
// Mock hooks
// ============================================================================
const mockUseProject = vi.fn();
vi.mock('@/hooks/use-projects', () => ({
  useProject: () => mockUseProject(),
}));

const mockUseClusters = vi.fn();
vi.mock('@/hooks/useClusters', () => ({
  useClusters: () => mockUseClusters(),
}));

const mockUseBlogCampaigns = vi.fn();
const mockCreateBlogCampaignMutate = vi.fn();
const mockUseCreateBlogCampaign = vi.fn();
vi.mock('@/hooks/useBlogs', () => ({
  useBlogCampaigns: () => mockUseBlogCampaigns(),
  useCreateBlogCampaign: () => mockUseCreateBlogCampaign(),
}));

// ============================================================================
// Default mock values
// ============================================================================
const mockProject = {
  id: 'proj-1',
  name: 'Test Project',
  site_url: 'https://example.com',
  brand_config_status: 'pending',
  has_brand_config: false,
  uploaded_files_count: 0,
};

const defaultMockProject = () => ({
  data: mockProject,
  isLoading: false,
  error: null,
});

const defaultMockCreateBlogCampaign = (overrides?: Record<string, unknown>) => ({
  mutate: mockCreateBlogCampaignMutate,
  isPending: false,
  isError: false,
  error: null,
  ...overrides,
});

// ============================================================================
// Mock data helpers
// ============================================================================
const createMockCluster = (
  id: string,
  name: string,
  seedKeyword: string,
  status: string,
  pageCount: number,
  approvedCount = 0,
): ClusterListItem => ({
  id,
  name,
  seed_keyword: seedKeyword,
  status,
  page_count: pageCount,
  approved_count: approvedCount,
  created_at: '2026-01-15T10:00:00Z',
});

const createMockBlogCampaign = (
  id: string,
  name: string,
  status: string,
  clusterName: string,
  postCount: number,
  approvedCount = 0,
  contentCompleteCount = 0,
): BlogCampaignListItem => ({
  id,
  name,
  status,
  cluster_name: clusterName,
  post_count: postCount,
  approved_count: approvedCount,
  content_complete_count: contentCompleteCount,
  created_at: '2026-01-20T10:00:00Z',
});

// ============================================================================
// Tests
// ============================================================================
describe('NewBlogCampaignPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProject.mockReturnValue(defaultMockProject());
    mockUseClusters.mockReturnValue({ data: [], isLoading: false, error: null });
    mockUseBlogCampaigns.mockReturnValue({ data: [], isLoading: false, error: null });
    mockUseCreateBlogCampaign.mockReturnValue(defaultMockCreateBlogCampaign());
  });

  // ============================================================================
  // Loading state
  // ============================================================================
  describe('loading state', () => {
    it('shows loading skeleton while data loads', () => {
      mockUseProject.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });

      render(<NewBlogCampaignPage />);

      expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Not found state
  // ============================================================================
  describe('not found state', () => {
    it('shows Project Not Found when project does not exist', () => {
      mockUseProject.mockReturnValue({
        data: null,
        isLoading: false,
        error: new Error('Not found'),
      });

      render(<NewBlogCampaignPage />);

      expect(screen.getByText('Project Not Found')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Form rendering
  // ============================================================================
  describe('form rendering', () => {
    it('renders "Create Blog Campaign" heading when loaded', () => {
      render(<NewBlogCampaignPage />);

      expect(screen.getByText('Create Blog Campaign')).toBeInTheDocument();
    });

    it('shows cluster dropdown with eligible clusters', () => {
      const clusters = [
        createMockCluster('c1', 'Running Shoes', 'running shoes', 'approved', 8, 8),
        createMockCluster('c2', 'Hiking Boots', 'hiking boots', 'complete', 5, 5),
      ];
      mockUseClusters.mockReturnValue({ data: clusters, isLoading: false, error: null });

      render(<NewBlogCampaignPage />);

      const select = screen.getByLabelText(/Parent Cluster/i);
      expect(select).toBeInTheDocument();

      // Eligible clusters should appear as selectable options
      expect(screen.getByText('Running Shoes')).toBeInTheDocument();
      expect(screen.getByText('Hiking Boots')).toBeInTheDocument();
    });

    it('shows ineligible clusters as disabled options with reason', () => {
      const clusters = [
        createMockCluster('c1', 'Running Shoes', 'running shoes', 'approved', 8, 8),
        createMockCluster('c2', 'Pending Cluster', 'pending kw', 'generating', 0, 0),
      ];
      mockUseClusters.mockReturnValue({ data: clusters, isLoading: false, error: null });

      render(<NewBlogCampaignPage />);

      // The ineligible cluster should be disabled and show reason
      const disabledOption = screen.getByText(/Pending Cluster/);
      expect(disabledOption.closest('option')).toBeDisabled();
      expect(disabledOption.textContent).toContain('Content not ready');
    });
  });

  // ============================================================================
  // Validation
  // ============================================================================
  describe('validation', () => {
    it('disables "Discover Topics" button when no cluster selected', () => {
      render(<NewBlogCampaignPage />);

      expect(
        screen.getByRole('button', { name: /Discover Topics/i })
      ).toHaveAttribute('aria-disabled', 'true');
    });

    it('shows validation error "Please select a cluster" on submit without selection', () => {
      render(<NewBlogCampaignPage />);

      // The mock Button uses aria-disabled instead of native disabled,
      // so clicks fire and handleSubmit calls validate() which sets the error.
      const submitButton = screen.getByRole('button', { name: /Discover Topics/i });
      fireEvent.click(submitButton);

      expect(screen.getByText('Please select a cluster')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Submission
  // ============================================================================
  describe('submission', () => {
    it('calls createBlogCampaign.mutate with correct args on valid submit', async () => {
      const user = userEvent.setup();

      const clusters = [
        createMockCluster('c1', 'Running Shoes', 'running shoes', 'approved', 8, 8),
      ];
      mockUseClusters.mockReturnValue({ data: clusters, isLoading: false, error: null });

      render(<NewBlogCampaignPage />);

      // Select a cluster
      const select = screen.getByLabelText(/Parent Cluster/i);
      await user.selectOptions(select, 'c1');

      // Click submit
      await user.click(screen.getByRole('button', { name: /Discover Topics/i }));

      expect(mockCreateBlogCampaignMutate).toHaveBeenCalledWith(
        {
          projectId: 'proj-1',
          data: {
            cluster_id: 'c1',
            name: undefined,
          },
        },
        expect.objectContaining({
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        }),
      );
    });
  });
});
