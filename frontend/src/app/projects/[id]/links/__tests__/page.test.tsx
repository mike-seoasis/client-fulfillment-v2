import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import OnboardingLinksPage from '../page';

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

const mockUseContentGeneration = vi.fn();
vi.mock('@/hooks/useContentGeneration', () => ({
  useContentGeneration: () => mockUseContentGeneration(),
}));

const mockPlanLinksMutation = {
  mutateAsync: vi.fn(),
  isPending: false,
};

const mockUsePlanStatus = vi.fn();

vi.mock('@/hooks/useLinks', () => ({
  usePlanLinks: () => mockPlanLinksMutation,
  usePlanStatus: () => mockUsePlanStatus(),
}));

// ============================================================================
// Test wrapper with QueryClientProvider
// ============================================================================
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

// ============================================================================
// Mock data factories
// ============================================================================
const mockProject = {
  id: 'test-project-123',
  name: 'Test Project',
  site_url: 'https://example.com',
};

const defaultProjectReturn = () => ({
  data: mockProject,
  isLoading: false,
  error: null,
});

interface ContentGenPage {
  is_approved: boolean;
  status: string;
  qa_passed: boolean | null;
  source: string;
}

const createContentGenData = (
  pages: ContentGenPage[] = [],
  overrides: Record<string, unknown> = {}
) => ({
  isLoading: false,
  pages,
  ...overrides,
});

const createPlanStatusData = (overrides: Record<string, unknown> = {}) => ({
  data: {
    status: 'idle' as string,
    current_step: null as number | null,
    step_label: null as string | null,
    pages_processed: 0,
    total_pages: 0,
    total_links: null as number | null,
    error: null as string | null,
    ...overrides,
  },
  isLoading: false,
});

// ============================================================================
// Tests
// ============================================================================
describe('OnboardingLinksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProject.mockReturnValue(defaultProjectReturn());
    mockUseContentGeneration.mockReturnValue(
      createContentGenData([
        { is_approved: true, status: 'complete', qa_passed: true, source: 'onboarding' },
        { is_approved: true, status: 'complete', qa_passed: true, source: 'onboarding' },
      ])
    );
    mockUsePlanStatus.mockReturnValue(createPlanStatusData());
    mockPlanLinksMutation.mutateAsync.mockResolvedValue({});
    mockPlanLinksMutation.isPending = false;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // --------------------------------------------------------------------------
  // Rendering
  // --------------------------------------------------------------------------
  describe('rendering', () => {
    it('displays the page title and breadcrumb', () => {
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      // Title contains both "Internal Links" and "Onboarding Pages" via mdash
      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveTextContent(/Internal Links/);
      expect(heading).toHaveTextContent(/Onboarding Pages/);
    });

    it('displays breadcrumb with project name', () => {
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });

    it('displays loading skeleton when project is loading', () => {
      mockUseProject.mockReturnValue({ data: null, isLoading: true, error: null });
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.getByText('All Projects')).toBeInTheDocument();
      expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
    });

    it('displays not found state when project errors', () => {
      mockUseProject.mockReturnValue({ data: null, isLoading: false, error: new Error('Not found') });
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.getByText('Project Not Found')).toBeInTheDocument();
      expect(screen.getByText('Back to Dashboard')).toBeInTheDocument();
    });

    it('displays link rules section', () => {
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.getByText('Link Rules (applied automatically):')).toBeInTheDocument();
      expect(screen.getByText(/Priority pages receive more inbound links/)).toBeInTheDocument();
      expect(screen.getByText(/Links stay within onboarding pages only/)).toBeInTheDocument();
    });

    it('displays back to project button', () => {
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.getByText('Back to Project')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Prerequisites rendering
  // --------------------------------------------------------------------------
  describe('prerequisites', () => {
    it('shows all prerequisites as passed when all met', () => {
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.getByText('Prerequisites')).toBeInTheDocument();
      expect(screen.getByText('All pages have approved keywords')).toBeInTheDocument();
      expect(screen.getByText(/All content generated/)).toBeInTheDocument();
    });

    it('shows keywords prerequisite as failed when not all approved', () => {
      mockUseContentGeneration.mockReturnValue(
        createContentGenData([
          { is_approved: false, status: 'complete', qa_passed: true, source: 'onboarding' },
          { is_approved: true, status: 'complete', qa_passed: true, source: 'onboarding' },
        ])
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      const text = screen.getByText('All pages have approved keywords');
      expect(text).toHaveClass('text-warm-gray-500');
    });

    it('shows content generation prerequisite as failed when incomplete', () => {
      mockUseContentGeneration.mockReturnValue(
        createContentGenData([
          { is_approved: true, status: 'complete', qa_passed: true, source: 'onboarding' },
          { is_approved: true, status: 'pending', qa_passed: null, source: 'onboarding' },
        ])
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.getByText(/1\/2 complete/)).toBeInTheDocument();
    });

    it('only counts onboarding pages for prerequisites', () => {
      mockUseContentGeneration.mockReturnValue(
        createContentGenData([
          { is_approved: true, status: 'complete', qa_passed: true, source: 'onboarding' },
          { is_approved: true, status: 'complete', qa_passed: true, source: 'onboarding' },
          { is_approved: true, status: 'complete', qa_passed: true, source: 'cluster' },
          { is_approved: false, status: 'pending', qa_passed: null, source: 'cluster' },
        ])
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      // Should show 2/2 (onboarding only), not 3/4
      expect(screen.getByText(/2\/2 complete/)).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Button disabled/enabled
  // --------------------------------------------------------------------------
  describe('plan button', () => {
    it('is enabled when all prerequisites are met', () => {
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      const button = screen.getByRole('button', { name: 'Plan & Inject Links' });
      expect(button).not.toBeDisabled();
    });

    it('is disabled when prerequisites are not met', () => {
      mockUseContentGeneration.mockReturnValue(
        createContentGenData([
          { is_approved: false, status: 'pending', qa_passed: null, source: 'onboarding' },
        ])
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      const button = screen.getByRole('button', { name: 'Plan & Inject Links' });
      expect(button).toBeDisabled();
    });

    it('is disabled when mutation is pending', () => {
      mockPlanLinksMutation.isPending = true;
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      const button = screen.getByRole('button', { name: /Starting/ });
      expect(button).toBeDisabled();
    });

    it('calls planLinks mutation on click', async () => {
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Plan & Inject Links' }));
      });
      expect(mockPlanLinksMutation.mutateAsync).toHaveBeenCalledWith({
        projectId: 'test-project-123',
        scope: 'onboarding',
      });
    });

    it('is hidden when planning is in progress', () => {
      mockUsePlanStatus.mockReturnValue(
        createPlanStatusData({ status: 'planning', current_step: 1, total_pages: 10 })
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.queryByRole('button', { name: 'Plan & Inject Links' })).not.toBeInTheDocument();
    });

    it('is hidden when planning is complete', () => {
      mockUsePlanStatus.mockReturnValue(
        createPlanStatusData({ status: 'complete', total_links: 15 })
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.queryByRole('button', { name: 'Plan & Inject Links' })).not.toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Progress indicator
  // --------------------------------------------------------------------------
  describe('progress indicator', () => {
    it('displays 4 pipeline steps during planning', () => {
      mockUsePlanStatus.mockReturnValue(
        createPlanStatusData({
          status: 'planning',
          current_step: 2,
          total_pages: 10,
          pages_processed: 3,
        })
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.getByText('Building link graph')).toBeInTheDocument();
      expect(screen.getByText('Selecting targets & anchor text')).toBeInTheDocument();
      expect(screen.getByText('Injecting links into content')).toBeInTheDocument();
      expect(screen.getByText('Validating link rules')).toBeInTheDocument();
    });

    it('shows step count during planning', () => {
      mockUsePlanStatus.mockReturnValue(
        createPlanStatusData({
          status: 'planning',
          current_step: 3,
          total_pages: 10,
          pages_processed: 5,
        })
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.getByText('Step 3 of 4')).toBeInTheDocument();
    });

    it('shows page progress for steps 2 and 3', () => {
      mockUsePlanStatus.mockReturnValue(
        createPlanStatusData({
          status: 'planning',
          current_step: 2,
          total_pages: 10,
          pages_processed: 3,
        })
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.getByText('(3/10 pages)')).toBeInTheDocument();
    });

    it('does not show page progress for step 1', () => {
      mockUsePlanStatus.mockReturnValue(
        createPlanStatusData({
          status: 'planning',
          current_step: 1,
          total_pages: 10,
          pages_processed: 0,
        })
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.queryByText(/pages\)/)).not.toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Completion and failure states
  // --------------------------------------------------------------------------
  describe('completion', () => {
    it('displays completion message with link count', () => {
      mockUsePlanStatus.mockReturnValue(
        createPlanStatusData({ status: 'complete', total_links: 42 })
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.getByText(/Link planning complete!/)).toBeInTheDocument();
      expect(screen.getByText(/42 links created/)).toBeInTheDocument();
      expect(screen.getByText(/Redirecting to link map/)).toBeInTheDocument();
    });

    it('triggers redirect to link map on completion', () => {
      vi.useFakeTimers();
      mockUsePlanStatus.mockReturnValue(
        createPlanStatusData({ status: 'complete', total_links: 10 })
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });

      act(() => {
        vi.advanceTimersByTime(1500);
      });

      expect(mockRouterPush).toHaveBeenCalledWith('/projects/test-project-123/links/map');
    });
  });

  describe('failure', () => {
    it('displays failure message with error', () => {
      mockUsePlanStatus.mockReturnValue(
        createPlanStatusData({ status: 'failed', error: 'API timeout' })
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.getByText(/Link planning failed/)).toBeInTheDocument();
      expect(screen.getByText(/API timeout/)).toBeInTheDocument();
    });

    it('shows retry button on failure', () => {
      mockUsePlanStatus.mockReturnValue(
        createPlanStatusData({ status: 'failed', error: 'Something went wrong' })
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    });

    it('calls planLinks on retry click', async () => {
      mockUsePlanStatus.mockReturnValue(
        createPlanStatusData({ status: 'failed', error: 'Error' })
      );
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
      });
      expect(mockPlanLinksMutation.mutateAsync).toHaveBeenCalledWith({
        projectId: 'test-project-123',
        scope: 'onboarding',
      });
    });
  });

  // --------------------------------------------------------------------------
  // Toast notifications
  // --------------------------------------------------------------------------
  describe('toast notifications', () => {
    it('shows success toast on plan start', async () => {
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Plan & Inject Links' }));
      });
      expect(screen.getByText('Link planning started')).toBeInTheDocument();
    });

    it('shows error toast on plan failure', async () => {
      mockPlanLinksMutation.mutateAsync.mockRejectedValue(new Error('Server error'));
      render(<OnboardingLinksPage />, { wrapper: createWrapper() });
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Plan & Inject Links' }));
      });
      expect(screen.getByText('Server error')).toBeInTheDocument();
    });
  });
});
