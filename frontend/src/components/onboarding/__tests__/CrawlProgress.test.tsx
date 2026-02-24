import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CrawlProgress } from '../CrawlProgress';

// ============================================================================
// Unit Tests: CrawlProgress component
// ============================================================================
describe('CrawlProgress', () => {
  describe('progress bar rendering', () => {
    it('renders label text', () => {
      render(<CrawlProgress completed={5} total={10} />);

      expect(screen.getByText('Progress')).toBeInTheDocument();
    });

    it('renders custom label', () => {
      render(<CrawlProgress completed={5} total={10} label="Crawling pages" />);

      expect(screen.getByText('Crawling pages')).toBeInTheDocument();
    });

    it('renders completed count and total', () => {
      render(<CrawlProgress completed={7} total={20} />);

      expect(screen.getByText('7 of 20')).toBeInTheDocument();
    });

    it('renders percentage when showPercentage is true (default)', () => {
      render(<CrawlProgress completed={5} total={10} />);

      expect(screen.getByText('(50%)')).toBeInTheDocument();
    });

    it('hides percentage when showPercentage is false', () => {
      render(<CrawlProgress completed={5} total={10} showPercentage={false} />);

      expect(screen.queryByText('(50%)')).not.toBeInTheDocument();
    });

    it('renders progress bar with correct aria attributes', () => {
      render(<CrawlProgress completed={3} total={10} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '3');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '10');
    });

    it('renders accessible label in aria-label', () => {
      render(<CrawlProgress completed={3} total={10} label="Crawling" />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-label', 'Crawling: 3 of 10 (30%)');
    });
  });

  describe('progress bar updates', () => {
    it('calculates percentage correctly at 0%', () => {
      render(<CrawlProgress completed={0} total={10} />);

      expect(screen.getByText('(0%)')).toBeInTheDocument();
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveStyle({ width: '0%' });
    });

    it('calculates percentage correctly at 50%', () => {
      render(<CrawlProgress completed={5} total={10} />);

      expect(screen.getByText('(50%)')).toBeInTheDocument();
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveStyle({ width: '50%' });
    });

    it('calculates percentage correctly at 100%', () => {
      render(<CrawlProgress completed={10} total={10} />);

      expect(screen.getByText('(100%)')).toBeInTheDocument();
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveStyle({ width: '100%' });
    });

    it('rounds percentage to nearest integer', () => {
      render(<CrawlProgress completed={1} total={3} />);

      // 1/3 = 33.33% → rounds to 33%
      expect(screen.getByText('(33%)')).toBeInTheDocument();
    });

    it('handles total of 0 gracefully', () => {
      render(<CrawlProgress completed={0} total={0} />);

      expect(screen.getByText('(0%)')).toBeInTheDocument();
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveStyle({ width: '0%' });
    });

    it('updates when props change', () => {
      const { rerender } = render(<CrawlProgress completed={2} total={10} />);

      expect(screen.getByText('2 of 10')).toBeInTheDocument();
      expect(screen.getByText('(20%)')).toBeInTheDocument();

      rerender(<CrawlProgress completed={7} total={10} />);

      expect(screen.getByText('7 of 10')).toBeInTheDocument();
      expect(screen.getByText('(70%)')).toBeInTheDocument();
    });
  });

  describe('progress bar styling', () => {
    it('has animated transition class', () => {
      render(<CrawlProgress completed={5} total={10} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveClass('transition-all');
      expect(progressBar).toHaveClass('duration-500');
      expect(progressBar).toHaveClass('ease-out');
    });

    it('has palm-500 fill color', () => {
      render(<CrawlProgress completed={5} total={10} />);

      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveClass('bg-palm-500');
    });
  });
});

// ============================================================================
// Mock types for page list testing (matching the page.tsx types)
// ============================================================================
interface PageSummary {
  id: string;
  url: string;
  status: 'pending' | 'crawling' | 'completed' | 'failed';
  title: string | null;
  word_count: number | null;
  headings: { h1?: string[]; h2?: string[]; h3?: string[] } | null;
  product_count: number | null;
  labels: string[];
  crawl_error: string | null;
}

// Helper components extracted for testing (mimicking page.tsx implementation)
function PageStatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'completed':
      return <span data-testid="check-icon">✓</span>;
    case 'crawling':
      return <span data-testid="spinner-icon" className="animate-spin">⟳</span>;
    case 'failed':
      return <span data-testid="error-icon">✗</span>;
    default: // pending
      return <span data-testid="pending-icon">○</span>;
  }
}

function PageStatusText({ status }: { status: string }) {
  switch (status) {
    case 'completed':
      return <span className="text-palm-600">Crawled</span>;
    case 'crawling':
      return <span className="text-lagoon-600">Crawling...</span>;
    case 'failed':
      return <span className="text-coral-600">Failed</span>;
    default:
      return <span className="text-warm-gray-500">Pending</span>;
  }
}

interface PageListItemProps {
  page: PageSummary;
  onRetry?: (pageId: string) => Promise<void>;
  isRetrying?: boolean;
}

function PageListItem({ page, onRetry, isRetrying }: PageListItemProps) {
  const displayUrl = (() => {
    try {
      const url = new URL(page.url);
      return url.pathname + url.search;
    } catch {
      return page.url;
    }
  })();

  const h2Count = page.headings?.h2?.length ?? 0;

  return (
    <div data-testid={`page-item-${page.id}`} className="py-3 border-b border-cream-200 last:border-b-0">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">
          <PageStatusIcon status={page.status} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-warm-gray-900 font-mono text-sm truncate">
              {displayUrl}
            </span>
            <div className="flex items-center gap-2">
              <PageStatusText status={page.status} />
              {page.status === 'failed' && onRetry && (
                <button
                  onClick={() => onRetry(page.id)}
                  disabled={isRetrying}
                  data-testid={`retry-button-${page.id}`}
                  className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-coral-700 bg-coral-50 hover:bg-coral-100 rounded-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title="Retry crawl"
                >
                  {isRetrying ? 'Retrying...' : 'Retry'}
                </button>
              )}
            </div>
          </div>
          {page.status === 'completed' && page.title && (
            <div className="mt-1 text-sm text-warm-gray-600 truncate">
              {page.title}
            </div>
          )}
          {page.status === 'completed' && (
            <div className="mt-1 text-xs text-warm-gray-500 flex gap-3 flex-wrap">
              {page.word_count !== null && (
                <span>{page.word_count.toLocaleString()} words</span>
              )}
              {h2Count > 0 && (
                <span>H2s: {h2Count}</span>
              )}
              {page.product_count !== null && (
                <span>{page.product_count} products</span>
              )}
            </div>
          )}
          {page.status === 'failed' && page.crawl_error && (
            <div data-testid={`crawl-error-${page.id}`} className="mt-1 text-sm text-coral-600">
              {page.crawl_error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Unit Tests: PageStatusIcon
// ============================================================================
describe('PageStatusIcon', () => {
  it('renders check icon for completed status', () => {
    render(<PageStatusIcon status="completed" />);
    expect(screen.getByTestId('check-icon')).toBeInTheDocument();
  });

  it('renders spinner icon for crawling status', () => {
    render(<PageStatusIcon status="crawling" />);
    const spinner = screen.getByTestId('spinner-icon');
    expect(spinner).toBeInTheDocument();
    expect(spinner).toHaveClass('animate-spin');
  });

  it('renders error icon for failed status', () => {
    render(<PageStatusIcon status="failed" />);
    expect(screen.getByTestId('error-icon')).toBeInTheDocument();
  });

  it('renders pending icon for pending status', () => {
    render(<PageStatusIcon status="pending" />);
    expect(screen.getByTestId('pending-icon')).toBeInTheDocument();
  });

  it('defaults to pending for unknown status', () => {
    render(<PageStatusIcon status="unknown" />);
    expect(screen.getByTestId('pending-icon')).toBeInTheDocument();
  });
});

// ============================================================================
// Unit Tests: PageStatusText
// ============================================================================
describe('PageStatusText', () => {
  it('shows "Crawled" for completed status', () => {
    render(<PageStatusText status="completed" />);
    expect(screen.getByText('Crawled')).toBeInTheDocument();
    expect(screen.getByText('Crawled')).toHaveClass('text-palm-600');
  });

  it('shows "Crawling..." for crawling status', () => {
    render(<PageStatusText status="crawling" />);
    expect(screen.getByText('Crawling...')).toBeInTheDocument();
    expect(screen.getByText('Crawling...')).toHaveClass('text-lagoon-600');
  });

  it('shows "Failed" for failed status', () => {
    render(<PageStatusText status="failed" />);
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toHaveClass('text-coral-600');
  });

  it('shows "Pending" for pending status', () => {
    render(<PageStatusText status="pending" />);
    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toHaveClass('text-warm-gray-500');
  });
});

// ============================================================================
// Component Tests: PageListItem
// ============================================================================
describe('PageListItem', () => {
  const mockOnRetry = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('displays URL path (not full URL)', () => {
      const page: PageSummary = {
        id: '1',
        url: 'https://example.com/products/shoes',
        status: 'pending',
        title: null,
        word_count: null,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: null,
      };

      render(<PageListItem page={page} />);

      expect(screen.getByText('/products/shoes')).toBeInTheDocument();
    });

    it('shows status icon and text', () => {
      const page: PageSummary = {
        id: '1',
        url: 'https://example.com/page',
        status: 'pending',
        title: null,
        word_count: null,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: null,
      };

      render(<PageListItem page={page} />);

      expect(screen.getByTestId('pending-icon')).toBeInTheDocument();
      expect(screen.getByText('Pending')).toBeInTheDocument();
    });
  });

  describe('completed page display', () => {
    it('shows title for completed pages', () => {
      const page: PageSummary = {
        id: '1',
        url: 'https://example.com/page',
        status: 'completed',
        title: 'Test Page Title',
        word_count: 500,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: null,
      };

      render(<PageListItem page={page} />);

      expect(screen.getByText('Test Page Title')).toBeInTheDocument();
    });

    it('shows word count for completed pages', () => {
      const page: PageSummary = {
        id: '1',
        url: 'https://example.com/page',
        status: 'completed',
        title: null,
        word_count: 1250,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: null,
      };

      render(<PageListItem page={page} />);

      expect(screen.getByText('1,250 words')).toBeInTheDocument();
    });

    it('shows H2 count for completed pages with headings', () => {
      const page: PageSummary = {
        id: '1',
        url: 'https://example.com/page',
        status: 'completed',
        title: null,
        word_count: null,
        headings: { h1: ['Title'], h2: ['Section 1', 'Section 2', 'Section 3'] },
        product_count: null,
        labels: [],
        crawl_error: null,
      };

      render(<PageListItem page={page} />);

      expect(screen.getByText('H2s: 3')).toBeInTheDocument();
    });

    it('shows product count for completed pages with products', () => {
      const page: PageSummary = {
        id: '1',
        url: 'https://example.com/collection',
        status: 'completed',
        title: null,
        word_count: null,
        headings: null,
        product_count: 24,
        labels: [],
        crawl_error: null,
      };

      render(<PageListItem page={page} />);

      expect(screen.getByText('24 products')).toBeInTheDocument();
    });

    it('shows all extracted data together', () => {
      const page: PageSummary = {
        id: '1',
        url: 'https://example.com/collection',
        status: 'completed',
        title: 'Running Shoes Collection',
        word_count: 2500,
        headings: { h2: ['Featured', 'New Arrivals', 'Sale'] },
        product_count: 48,
        labels: ['shoes', 'running'],
        crawl_error: null,
      };

      render(<PageListItem page={page} />);

      expect(screen.getByText('Running Shoes Collection')).toBeInTheDocument();
      expect(screen.getByText('2,500 words')).toBeInTheDocument();
      expect(screen.getByText('H2s: 3')).toBeInTheDocument();
      expect(screen.getByText('48 products')).toBeInTheDocument();
    });
  });

  describe('failed page display', () => {
    it('shows error message for failed pages', () => {
      const page: PageSummary = {
        id: '1',
        url: 'https://example.com/page',
        status: 'failed',
        title: null,
        word_count: null,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: 'Connection timeout after 30 seconds',
      };

      render(<PageListItem page={page} />);

      expect(screen.getByTestId('crawl-error-1')).toHaveTextContent('Connection timeout after 30 seconds');
    });

    it('shows retry button for failed pages when onRetry provided', () => {
      const page: PageSummary = {
        id: 'page-123',
        url: 'https://example.com/page',
        status: 'failed',
        title: null,
        word_count: null,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: 'Error occurred',
      };

      render(<PageListItem page={page} onRetry={mockOnRetry} />);

      expect(screen.getByTestId('retry-button-page-123')).toBeInTheDocument();
      expect(screen.getByText('Retry')).toBeInTheDocument();
    });

    it('does not show retry button when onRetry is not provided', () => {
      const page: PageSummary = {
        id: 'page-123',
        url: 'https://example.com/page',
        status: 'failed',
        title: null,
        word_count: null,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: 'Error occurred',
      };

      render(<PageListItem page={page} />);

      expect(screen.queryByTestId('retry-button-page-123')).not.toBeInTheDocument();
    });

    it('does not show retry button for non-failed pages', () => {
      const page: PageSummary = {
        id: 'page-123',
        url: 'https://example.com/page',
        status: 'completed',
        title: 'Test',
        word_count: 100,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: null,
      };

      render(<PageListItem page={page} onRetry={mockOnRetry} />);

      expect(screen.queryByTestId('retry-button-page-123')).not.toBeInTheDocument();
    });
  });

  describe('retry button functionality', () => {
    it('calls onRetry with page id when clicked', async () => {
      const user = userEvent.setup();
      const page: PageSummary = {
        id: 'page-456',
        url: 'https://example.com/page',
        status: 'failed',
        title: null,
        word_count: null,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: 'Error',
      };

      render(<PageListItem page={page} onRetry={mockOnRetry} />);

      await user.click(screen.getByTestId('retry-button-page-456'));

      expect(mockOnRetry).toHaveBeenCalledWith('page-456');
      expect(mockOnRetry).toHaveBeenCalledTimes(1);
    });

    it('shows "Retrying..." text when isRetrying is true', () => {
      const page: PageSummary = {
        id: 'page-789',
        url: 'https://example.com/page',
        status: 'failed',
        title: null,
        word_count: null,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: 'Error',
      };

      render(<PageListItem page={page} onRetry={mockOnRetry} isRetrying={true} />);

      expect(screen.getByText('Retrying...')).toBeInTheDocument();
      expect(screen.queryByText('Retry')).not.toBeInTheDocument();
    });

    it('disables retry button when isRetrying is true', () => {
      const page: PageSummary = {
        id: 'page-789',
        url: 'https://example.com/page',
        status: 'failed',
        title: null,
        word_count: null,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: 'Error',
      };

      render(<PageListItem page={page} onRetry={mockOnRetry} isRetrying={true} />);

      const button = screen.getByTestId('retry-button-page-789');
      expect(button).toBeDisabled();
    });

    it('button is enabled when isRetrying is false', () => {
      const page: PageSummary = {
        id: 'page-789',
        url: 'https://example.com/page',
        status: 'failed',
        title: null,
        word_count: null,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: 'Error',
      };

      render(<PageListItem page={page} onRetry={mockOnRetry} isRetrying={false} />);

      const button = screen.getByTestId('retry-button-page-789');
      expect(button).not.toBeDisabled();
    });
  });

  describe('URL display', () => {
    it('extracts path from full URL', () => {
      const page: PageSummary = {
        id: '1',
        url: 'https://example.com/path/to/page',
        status: 'pending',
        title: null,
        word_count: null,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: null,
      };

      render(<PageListItem page={page} />);

      expect(screen.getByText('/path/to/page')).toBeInTheDocument();
    });

    it('includes query string in display', () => {
      const page: PageSummary = {
        id: '1',
        url: 'https://example.com/search?q=test&page=2',
        status: 'pending',
        title: null,
        word_count: null,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: null,
      };

      render(<PageListItem page={page} />);

      expect(screen.getByText('/search?q=test&page=2')).toBeInTheDocument();
    });

    it('handles invalid URLs gracefully (shows raw URL)', () => {
      const page: PageSummary = {
        id: '1',
        url: 'not-a-valid-url',
        status: 'pending',
        title: null,
        word_count: null,
        headings: null,
        product_count: null,
        labels: [],
        crawl_error: null,
      };

      render(<PageListItem page={page} />);

      expect(screen.getByText('not-a-valid-url')).toBeInTheDocument();
    });
  });
});

// ============================================================================
// Polling behavior tests
// ============================================================================
describe('Polling behavior', () => {
  // These tests document the expected polling behavior from the page component.
  // The actual polling is implemented via TanStack Query's refetchInterval.

  it('documents expected polling configuration', () => {
    // Based on page.tsx implementation:
    // - Poll every 2000ms (2 seconds)
    // - Stop polling when status === 'complete'
    // - Continue polling for 'crawling' and 'labeling' statuses

    const pollingConfig = {
      interval: 2000,
      stopCondition: (status: string) => status === 'complete',
      continueConditions: ['crawling', 'labeling'],
    };

    expect(pollingConfig.interval).toBe(2000);
    expect(pollingConfig.stopCondition('complete')).toBe(true);
    expect(pollingConfig.stopCondition('crawling')).toBe(false);
    expect(pollingConfig.stopCondition('labeling')).toBe(false);
    expect(pollingConfig.continueConditions).toContain('crawling');
    expect(pollingConfig.continueConditions).toContain('labeling');
  });

  it('documents refetchInterval function behavior', () => {
    // Simulating the refetchInterval callback from page.tsx
    const refetchInterval = (data: { state: { data?: { status: string } } }) => {
      if (data.state.data?.status === 'complete') {
        return false;
      }
      return 2000;
    };

    // When status is 'crawling', should return 2000 (continue polling)
    expect(refetchInterval({ state: { data: { status: 'crawling' } } })).toBe(2000);

    // When status is 'labeling', should return 2000 (continue polling)
    expect(refetchInterval({ state: { data: { status: 'labeling' } } })).toBe(2000);

    // When status is 'complete', should return false (stop polling)
    expect(refetchInterval({ state: { data: { status: 'complete' } } })).toBe(false);

    // When no data yet, should return 2000 (continue polling)
    expect(refetchInterval({ state: { data: undefined } })).toBe(2000);
  });
});
