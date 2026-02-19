import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import NewClusterPage from '../page';

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

const mockCreateClusterMutate = vi.fn();
const mockCreateCluster = vi.fn();
vi.mock('@/hooks/useClusters', () => ({
  useCreateCluster: () => mockCreateCluster(),
}));

// ============================================================================
// Default mock values
// ============================================================================
const mockProject = {
  id: 'test-project-123',
  name: 'Test Project',
  site_url: 'https://example.com',
};

const defaultMockProject = () => ({
  data: mockProject,
  isLoading: false,
  error: null,
});

const defaultMockCreateCluster = (overrides?: Record<string, unknown>) => ({
  mutate: mockCreateClusterMutate,
  isPending: false,
  isError: false,
  error: null,
  ...overrides,
});

// ============================================================================
// Tests
// ============================================================================
describe('NewClusterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProject.mockReturnValue(defaultMockProject());
    mockCreateCluster.mockReturnValue(defaultMockCreateCluster());
  });

  // ============================================================================
  // Form rendering
  // ============================================================================
  describe('form rendering', () => {
    it('renders the seed keyword input field', () => {
      render(<NewClusterPage />);

      expect(screen.getByLabelText(/Seed Keyword/i)).toBeInTheDocument();
    });

    it('renders the cluster name input field', () => {
      render(<NewClusterPage />);

      expect(screen.getByLabelText(/Cluster Name/i)).toBeInTheDocument();
    });

    it('renders Get Suggestions button', () => {
      render(<NewClusterPage />);

      expect(screen.getByRole('button', { name: /Get Suggestions/i })).toBeInTheDocument();
    });

    it('renders Cancel button', () => {
      render(<NewClusterPage />);

      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
    });

    it('renders page title', () => {
      render(<NewClusterPage />);

      expect(screen.getByText('Create New Keyword Cluster')).toBeInTheDocument();
    });

    it('renders breadcrumb with project name', () => {
      render(<NewClusterPage />);

      expect(screen.getByText('Test Project')).toBeInTheDocument();
      expect(screen.getByText('New Cluster')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Validation
  // ============================================================================
  describe('validation', () => {
    it('Get Suggestions button is disabled when seed keyword is empty', () => {
      render(<NewClusterPage />);

      expect(screen.getByRole('button', { name: /Get Suggestions/i })).toBeDisabled();
    });

    it('Get Suggestions button is disabled when seed keyword is 1 character', async () => {
      const user = userEvent.setup();
      render(<NewClusterPage />);

      await user.type(screen.getByLabelText(/Seed Keyword/i), 'a');

      expect(screen.getByRole('button', { name: /Get Suggestions/i })).toBeDisabled();
    });

    it('Get Suggestions button is enabled when seed keyword is 2+ characters', async () => {
      const user = userEvent.setup();
      render(<NewClusterPage />);

      await user.type(screen.getByLabelText(/Seed Keyword/i), 'ab');

      expect(screen.getByRole('button', { name: /Get Suggestions/i })).not.toBeDisabled();
    });

    it('shows validation error when submitting with short keyword', async () => {
      const user = userEvent.setup();
      render(<NewClusterPage />);

      // Type a single character to enable button briefly, then clear
      const input = screen.getByLabelText(/Seed Keyword/i);
      await user.type(input, 'ab');
      await user.clear(input);
      await user.type(input, 'a');

      // Button should be disabled with 1 char
      expect(screen.getByRole('button', { name: /Get Suggestions/i })).toBeDisabled();
    });
  });

  // ============================================================================
  // Loading state
  // ============================================================================
  describe('loading state', () => {
    it('shows loading skeleton while project is loading', () => {
      mockUseProject.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });

      render(<NewClusterPage />);

      expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
      expect(screen.getByText('All Projects')).toBeInTheDocument();
    });

    it('shows progress indicator when mutation is pending', () => {
      mockCreateCluster.mockReturnValue(defaultMockCreateCluster({ isPending: true }));

      render(<NewClusterPage />);

      expect(screen.getByText('Generating suggestions...')).toBeInTheDocument();
      expect(screen.getByText('Checking search volume...')).toBeInTheDocument();
      expect(screen.getByText('Finalizing results...')).toBeInTheDocument();
    });

    it('hides form when mutation is pending', () => {
      mockCreateCluster.mockReturnValue(defaultMockCreateCluster({ isPending: true }));

      render(<NewClusterPage />);

      expect(screen.queryByLabelText(/Seed Keyword/i)).not.toBeInTheDocument();
    });
  });

  // ============================================================================
  // Submission
  // ============================================================================
  describe('submission', () => {
    it('calls createCluster.mutate with seed keyword on submit', async () => {
      const user = userEvent.setup();
      render(<NewClusterPage />);

      await user.type(screen.getByLabelText(/Seed Keyword/i), 'trail running shoes');
      await user.click(screen.getByRole('button', { name: /Get Suggestions/i }));

      expect(mockCreateClusterMutate).toHaveBeenCalledWith(
        {
          projectId: 'test-project-123',
          data: {
            seed_keyword: 'trail running shoes',
            name: undefined,
          },
        },
        expect.objectContaining({
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        })
      );
    });

    it('includes cluster name when provided', async () => {
      const user = userEvent.setup();
      render(<NewClusterPage />);

      await user.type(screen.getByLabelText(/Seed Keyword/i), 'trail running shoes');
      await user.type(screen.getByLabelText(/Cluster Name/i), 'Running Shoes Collection');
      await user.click(screen.getByRole('button', { name: /Get Suggestions/i }));

      expect(mockCreateClusterMutate).toHaveBeenCalledWith(
        {
          projectId: 'test-project-123',
          data: {
            seed_keyword: 'trail running shoes',
            name: 'Running Shoes Collection',
          },
        },
        expect.objectContaining({
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        })
      );
    });
  });

  // ============================================================================
  // Navigation
  // ============================================================================
  describe('navigation', () => {
    it('navigates to project page on success', async () => {
      const user = userEvent.setup();

      // Make mutate call the onSuccess callback immediately
      mockCreateClusterMutate.mockImplementation((_input: unknown, options: { onSuccess: (data: { id: string }) => void }) => {
        options.onSuccess({ id: 'new-cluster-456' });
      });

      render(<NewClusterPage />);

      await user.type(screen.getByLabelText(/Seed Keyword/i), 'trail running shoes');
      await user.click(screen.getByRole('button', { name: /Get Suggestions/i }));

      expect(mockRouterPush).toHaveBeenCalledWith(
        '/projects/test-project-123/clusters/new-cluster-456'
      );
    });

    it('Cancel button links back to project page', () => {
      render(<NewClusterPage />);

      const cancelLink = screen.getByRole('button', { name: /Cancel/i }).closest('a');
      expect(cancelLink).toHaveAttribute('href', '/projects/test-project-123');
    });
  });

  // ============================================================================
  // Error state
  // ============================================================================
  describe('error state', () => {
    it('shows error message when mutation fails', () => {
      mockCreateCluster.mockReturnValue(
        defaultMockCreateCluster({
          isError: true,
          error: { message: 'Server timeout' },
        })
      );

      render(<NewClusterPage />);

      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
      expect(screen.getByText('Server timeout')).toBeInTheDocument();
    });

    it('shows Try Again button on error', () => {
      mockCreateCluster.mockReturnValue(
        defaultMockCreateCluster({
          isError: true,
          error: { message: 'Server timeout' },
        })
      );

      render(<NewClusterPage />);

      expect(screen.getByRole('button', { name: /Try Again/i })).toBeInTheDocument();
    });

    it('shows Cancel button on error', () => {
      mockCreateCluster.mockReturnValue(
        defaultMockCreateCluster({
          isError: true,
          error: { message: 'Server timeout' },
        })
      );

      render(<NewClusterPage />);

      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Not found state
  // ============================================================================
  describe('not found state', () => {
    it('shows Project Not Found when project fetch fails', () => {
      mockUseProject.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Not found'),
      });

      render(<NewClusterPage />);

      expect(screen.getByText('Project Not Found')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Back to Dashboard' })).toBeInTheDocument();
    });

    it('shows Project Not Found when project is null', () => {
      mockUseProject.mockReturnValue({
        data: null,
        isLoading: false,
        error: null,
      });

      render(<NewClusterPage />);

      expect(screen.getByText('Project Not Found')).toBeInTheDocument();
    });
  });
});
