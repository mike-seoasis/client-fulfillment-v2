import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ClusterContentGenerationPage from '../page';

// ============================================================================
// Mock Next.js navigation
// ============================================================================
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'proj-1', clusterId: 'cluster-1' }),
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
vi.mock('@/hooks/use-projects', () => ({
  useProject: vi.fn(() => ({
    data: { id: 'proj-1', name: 'Test Project' },
    isLoading: false,
    error: null,
  })),
}));

vi.mock('@/hooks/useClusters', () => ({
  useCluster: vi.fn(() => ({
    data: { id: 'cluster-1', name: 'Test Cluster' },
    isLoading: false,
    error: null,
  })),
}));

const mockStartGenerationAsync = vi.fn();
const mockRegenerateAsync = vi.fn();

vi.mock('@/hooks/useContentGeneration', () => ({
  useContentGeneration: vi.fn(() => ({
    overallStatus: 'complete',
    isGenerating: false,
    isComplete: true,
    isFailed: false,
    isLoading: false,
    pagesTotal: 2,
    pagesCompleted: 2,
    pagesFailed: 0,
    pagesApproved: 1,
    progress: 100,
    pages: [
      {
        page_id: 'page-1',
        url: 'https://example.com/page-1',
        keyword: 'test keyword',
        status: 'complete',
        is_approved: false,
        qa_passed: true,
        qa_issue_count: 0,
        error: null,
      },
      {
        page_id: 'page-2',
        url: 'https://example.com/page-2',
        keyword: 'other keyword',
        status: 'complete',
        is_approved: true,
        qa_passed: true,
        qa_issue_count: 0,
        error: null,
      },
    ],
    startGenerationAsync: mockStartGenerationAsync,
    regenerateAsync: mockRegenerateAsync,
    isStarting: false,
    startError: null,
    refetch: vi.fn(),
    invalidate: vi.fn(),
    isError: false,
  })),
  useBulkApproveContent: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending: false,
  })),
}));

// Mock PromptInspector (renders nothing in tests)
vi.mock('@/components/PromptInspector', () => ({
  PromptInspector: () => null,
}));

// Mock UI components
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
  Toast: () => null,
}));

// ============================================================================
// Tests
// ============================================================================
describe('ClusterContentGenerationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --------------------------------------------------------------------------
  // No step indicator
  // --------------------------------------------------------------------------
  describe('does not render step indicator', () => {
    it('does not contain "Step" text in the document', () => {
      render(<ClusterContentGenerationPage />);
      expect(screen.queryByText(/Step \d/)).not.toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Breadcrumb shows cluster name
  // --------------------------------------------------------------------------
  describe('breadcrumb navigation', () => {
    it('shows project name in breadcrumb', () => {
      render(<ClusterContentGenerationPage />);
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });

    it('shows cluster name in breadcrumb', () => {
      render(<ClusterContentGenerationPage />);
      expect(screen.getByText('Test Cluster')).toBeInTheDocument();
    });

    it('shows Content label in breadcrumb', () => {
      render(<ClusterContentGenerationPage />);
      expect(screen.getByText('Content')).toBeInTheDocument();
    });

    it('does not show "Onboarding" in breadcrumb', () => {
      render(<ClusterContentGenerationPage />);
      expect(screen.queryByText('Onboarding')).not.toBeInTheDocument();
    });

    it('breadcrumb project link points to project page', () => {
      render(<ClusterContentGenerationPage />);
      const link = screen.getByText('Test Project').closest('a');
      expect(link).toHaveAttribute('href', '/projects/proj-1');
    });

    it('breadcrumb cluster link points to cluster detail page', () => {
      render(<ClusterContentGenerationPage />);
      const link = screen.getByText('Test Cluster').closest('a');
      expect(link).toHaveAttribute('href', '/projects/proj-1/clusters/cluster-1');
    });
  });

  // --------------------------------------------------------------------------
  // Links point to cluster content paths
  // --------------------------------------------------------------------------
  describe('links point to cluster content paths', () => {
    it('Review links point to cluster content detail paths', () => {
      render(<ClusterContentGenerationPage />);
      const reviewLinks = screen.getAllByText('Review');
      // Each review link should point to /projects/proj-1/clusters/cluster-1/content/{pageId}
      for (const link of reviewLinks) {
        const anchor = link.closest('a');
        expect(anchor).toBeTruthy();
        expect(anchor!.getAttribute('href')).toMatch(
          /\/projects\/proj-1\/clusters\/cluster-1\/content\/page-/
        );
      }
    });

    it('Review links do not point to onboarding paths', () => {
      render(<ClusterContentGenerationPage />);
      const reviewLinks = screen.getAllByText('Review');
      for (const link of reviewLinks) {
        const anchor = link.closest('a');
        expect(anchor!.getAttribute('href')).not.toContain('/onboarding/');
      }
    });
  });

  // --------------------------------------------------------------------------
  // Renders content generation UI elements
  // --------------------------------------------------------------------------
  describe('renders content generation UI elements', () => {
    it('displays the completion header', () => {
      render(<ClusterContentGenerationPage />);
      expect(screen.getByText('Content Generation Complete')).toBeInTheDocument();
    });

    it('displays completed pages count', () => {
      render(<ClusterContentGenerationPage />);
      expect(screen.getByText(/2 pages complete/)).toBeInTheDocument();
    });

    it('displays approval count', () => {
      render(<ClusterContentGenerationPage />);
      expect(screen.getByText(/1 of 2/)).toBeInTheDocument();
    });

    it('renders Needs Review tab', () => {
      render(<ClusterContentGenerationPage />);
      expect(screen.getByText('Needs Review')).toBeInTheDocument();
    });

    it('renders Approved tab', () => {
      render(<ClusterContentGenerationPage />);
      expect(screen.getByText('Approved')).toBeInTheDocument();
    });

    it('renders Regenerate All button when complete', () => {
      render(<ClusterContentGenerationPage />);
      expect(screen.getByText('Regenerate All')).toBeInTheDocument();
    });

    it('renders Continue to Export button when pages are approved', () => {
      render(<ClusterContentGenerationPage />);
      expect(screen.getByText('Continue to Export')).toBeInTheDocument();
    });

    it('renders Back button linking to cluster detail', () => {
      render(<ClusterContentGenerationPage />);
      const backLink = screen.getByText('Back').closest('a');
      expect(backLink).toHaveAttribute(
        'href',
        '/projects/proj-1/clusters/cluster-1'
      );
    });
  });
});
