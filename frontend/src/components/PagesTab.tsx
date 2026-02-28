'use client';

import { useState, useCallback, useEffect } from 'react';
import {
  useShopifyStatus,
  useShopifyPages,
  useShopifyPageCounts,
  useShopifySync,
} from '@/hooks/useShopify';
import { Button, Input } from '@/components/ui';
import type { ShopifyPage, ShopifyPageCounts } from '@/lib/api';

// =============================================================================
// Helper: relative time formatting
// =============================================================================

function formatRelativeTime(dateString: string): string {
  const now = Date.now();
  const then = new Date(dateString).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 30) return `${diffDay}d ago`;
  return new Date(dateString).toLocaleDateString();
}

// =============================================================================
// Icons
// =============================================================================

function LinkIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  );
}

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="9 12 12 15 16 10" />
    </svg>
  );
}

function CircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
    </svg>
  );
}

function ChevronLeftIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

function ChevronRightIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

// =============================================================================
// Category definitions
// =============================================================================

type CategoryKey = 'collection' | 'product' | 'article' | 'page';

interface CategoryDef {
  key: CategoryKey;
  label: string;
  labelPlural: string;
  searchPlaceholder: string;
  columns: { key: string; label: string }[];
}

const CATEGORIES: CategoryDef[] = [
  {
    key: 'collection',
    label: 'Collections',
    labelPlural: 'pages',
    searchPlaceholder: 'Search collections...',
    columns: [
      { key: 'title', label: 'Page' },
      { key: 'handle', label: 'Handle' },
      { key: 'product_count', label: 'Products' },
    ],
  },
  {
    key: 'product',
    label: 'Products',
    labelPlural: 'pages',
    searchPlaceholder: 'Search products...',
    columns: [
      { key: 'title', label: 'Page' },
      { key: 'product_type', label: 'Type' },
      { key: 'status', label: 'Status' },
    ],
  },
  {
    key: 'article',
    label: 'Blog Posts',
    labelPlural: 'posts',
    searchPlaceholder: 'Search blog posts...',
    columns: [
      { key: 'title', label: 'Title' },
      { key: 'blog_name', label: 'Blog' },
      { key: 'published_at', label: 'Published' },
    ],
  },
  {
    key: 'page',
    label: 'Pages',
    labelPlural: 'pages',
    searchPlaceholder: 'Search pages...',
    columns: [
      { key: 'title', label: 'Title' },
      { key: 'handle', label: 'Handle' },
      { key: 'status', label: 'Status' },
    ],
  },
];

// =============================================================================
// Not Connected State
// =============================================================================

function NotConnectedState({ projectId }: { projectId: string }) {
  const [showInput, setShowInput] = useState(false);
  const [storeDomain, setStoreDomain] = useState('');
  const [domainError, setDomainError] = useState('');

  const handleConnect = useCallback(() => {
    if (!showInput) {
      setShowInput(true);
      return;
    }

    const trimmed = storeDomain.trim();
    if (!trimmed) {
      setDomainError('Please enter your store domain');
      return;
    }

    // Validate .myshopify.com domain
    const domain = trimmed.includes('.myshopify.com')
      ? trimmed
      : `${trimmed}.myshopify.com`;

    if (!/^[a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com$/.test(domain)) {
      setDomainError('Enter a valid Shopify domain (e.g., yourstore.myshopify.com)');
      return;
    }

    setDomainError('');
    // Redirect to OAuth install endpoint
    window.location.href = `/api/v1/shopify/auth/install?shop=${encodeURIComponent(domain)}&project_id=${encodeURIComponent(projectId)}`;
  }, [showInput, storeDomain, projectId]);

  return (
    <div className="flex items-center justify-center py-16">
      <div className="text-center max-w-md">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-palm-50 mb-6">
          <LinkIcon className="w-8 h-8 text-palm-500" />
        </div>

        <h2 className="text-xl font-semibold text-warm-gray-900 mb-3">
          Connect Your Shopify Store
        </h2>

        <p className="text-warm-gray-600 text-sm mb-6">
          Automatically sync your collections, products, blog posts, and pages from Shopify.
          Keep a live inventory of all your site content.
        </p>

        {showInput && (
          <div className="mb-4">
            <Input
              placeholder="yourstore.myshopify.com"
              value={storeDomain}
              onChange={(e) => {
                setStoreDomain(e.target.value);
                setDomainError('');
              }}
              error={domainError}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleConnect();
                }
              }}
            />
          </div>
        )}

        <Button onClick={handleConnect}>
          {showInput ? 'Continue' : 'Connect to Shopify'}
        </Button>

        <p className="text-warm-gray-400 text-xs mt-4">
          This will redirect you to Shopify to authorize read-only access to your store.
        </p>
      </div>
    </div>
  );
}

// =============================================================================
// Syncing State
// =============================================================================

const SYNC_RESOURCES = [
  { key: 'collections', label: 'Collections' },
  { key: 'products', label: 'Products' },
  { key: 'blog_posts', label: 'Blog Posts' },
  { key: 'pages', label: 'Pages' },
];

function SyncingState({ projectId, storeDomain }: { projectId: string; storeDomain?: string }) {
  const { data: status } = useShopifyStatus(projectId, {
    refetchInterval: 2000,
  });

  // The sync status from the backend will tell us if syncing is done.
  // For the UI, we show a simple progress indicator.
  // Since we don't get per-resource granularity from the status endpoint,
  // we simulate progress based on elapsed time.
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((p) => Math.min(p + 5, 90));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // If sync completes (status changes to idle), snap progress to 100
  useEffect(() => {
    if (status?.sync_status === 'idle' && status?.connected) {
      setProgress(100);
    }
  }, [status?.sync_status, status?.connected]);

  return (
    <div className="flex items-center justify-center py-16">
      <div className="text-center max-w-md">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-lagoon-50 mb-6">
          <SpinnerIcon className="w-8 h-8 text-lagoon-500" />
        </div>

        <h2 className="text-xl font-semibold text-warm-gray-900 mb-3">
          Syncing with {storeDomain || 'your store'}
        </h2>

        <p className="text-warm-gray-600 text-sm mb-6">
          Pulling your collections, products, blog posts, and pages.
          This usually takes under a minute.
        </p>

        {/* Progress bar */}
        <div className="w-full max-w-xs mx-auto mb-6">
          <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-palm-500 transition-all duration-500 ease-out rounded-full"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-warm-gray-500 mt-2">Fetching...</p>
        </div>

        {/* Resource status list */}
        <div className="text-left max-w-xs mx-auto space-y-2">
          {SYNC_RESOURCES.map((resource, index) => {
            // Simple heuristic: mark as done based on progress
            const isDone = progress > (index + 1) * 20;
            const isActive = !isDone && progress > index * 20;

            return (
              <div key={resource.key} className="flex items-center gap-2 text-sm">
                {isDone ? (
                  <CheckCircleIcon className="w-4 h-4 text-palm-500 flex-shrink-0" />
                ) : isActive ? (
                  <SpinnerIcon className="w-4 h-4 text-lagoon-500 flex-shrink-0" />
                ) : (
                  <CircleIcon className="w-4 h-4 text-cream-400 flex-shrink-0" />
                )}
                <span className={isDone ? 'text-warm-gray-900' : isActive ? 'text-lagoon-700' : 'text-warm-gray-400'}>
                  {resource.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Category Sidebar
// =============================================================================

function CategorySidebar({
  activeCategory,
  onCategoryChange,
  counts,
}: {
  activeCategory: CategoryKey;
  onCategoryChange: (key: CategoryKey) => void;
  counts: ShopifyPageCounts | undefined;
}) {
  return (
    <div className="w-48 flex-shrink-0">
      <p className="text-xs font-semibold text-warm-gray-400 uppercase tracking-wider mb-3 px-3">
        Categories
      </p>
      <nav className="space-y-1">
        {CATEGORIES.map((cat) => {
          const isActive = activeCategory === cat.key;
          const count = counts?.[cat.key] ?? 0;

          return (
            <button
              key={cat.key}
              onClick={() => onCategoryChange(cat.key)}
              className={`w-full text-left px-3 py-2 text-sm rounded-sm transition-colors ${
                isActive
                  ? 'border-l-2 border-palm-500 bg-palm-50 text-palm-700 font-medium'
                  : 'text-warm-gray-600 hover:bg-cream-100 border-l-2 border-transparent'
              }`}
            >
              <div className="flex items-center justify-between">
                <span>{cat.label}</span>
                <span className={`text-xs ${isActive ? 'text-palm-600' : 'text-warm-gray-400'}`}>
                  {count}
                </span>
              </div>
            </button>
          );
        })}
      </nav>
    </div>
  );
}

// =============================================================================
// Pages Table
// =============================================================================

function getCellValue(page: ShopifyPage, columnKey: string): string {
  switch (columnKey) {
    case 'title':
      return page.title || '(untitled)';
    case 'handle':
      return page.handle ? `/${page.handle}` : '';
    case 'product_count':
      return page.product_count != null ? String(page.product_count) : '-';
    case 'product_type':
      return page.product_type || '-';
    case 'status':
      return page.status ? page.status.charAt(0).toUpperCase() + page.status.slice(1) : '-';
    case 'blog_name':
      return page.blog_name || '-';
    case 'published_at':
      if (!page.published_at) return '-';
      return new Date(page.published_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
    default:
      return '-';
  }
}

function PagesTable({
  pages,
  columns,
  total,
  currentPage,
  perPage,
  onPageChange,
}: {
  pages: ShopifyPage[];
  columns: { key: string; label: string }[];
  total: number;
  currentPage: number;
  perPage: number;
  onPageChange: (page: number) => void;
}) {
  const startItem = (currentPage - 1) * perPage + 1;
  const endItem = Math.min(currentPage * perPage, total);
  const totalPages = Math.ceil(total / perPage);

  return (
    <div>
      {/* Table */}
      <div className="border border-cream-300 rounded-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-cream-50 border-b border-cream-300">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="text-left text-xs font-semibold text-warm-gray-500 uppercase tracking-wider px-4 py-3"
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pages.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="text-center text-warm-gray-500 text-sm py-8">
                  No results found
                </td>
              </tr>
            ) : (
              pages.map((page) => (
                <tr
                  key={page.id}
                  onClick={() => window.open(page.full_url, '_blank')}
                  className="border-b border-cream-200 last:border-b-0 hover:bg-cream-50 cursor-pointer transition-colors"
                >
                  {columns.map((col) => (
                    <td key={col.key} className="px-4 py-3 text-sm text-warm-gray-900">
                      {col.key === 'title' ? (
                        <span className="font-medium">{getCellValue(page, col.key)}</span>
                      ) : col.key === 'status' ? (
                        <StatusBadge status={getCellValue(page, col.key)} />
                      ) : (
                        <span className="text-warm-gray-600">{getCellValue(page, col.key)}</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > perPage && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-warm-gray-600">
            Showing {startItem}-{endItem} of {total}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage <= 1}
              className="p-1.5 rounded-sm border border-cream-300 text-warm-gray-600 hover:bg-cream-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeftIcon className="w-4 h-4" />
            </button>
            <span className="text-sm text-warm-gray-600 min-w-[60px] text-center">
              {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
              className="p-1.5 rounded-sm border border-cream-300 text-warm-gray-600 hover:bg-cream-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRightIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const lower = status.toLowerCase();
  let colorClasses = 'bg-cream-100 text-warm-gray-600';
  if (lower === 'active' || lower === 'published') {
    colorClasses = 'bg-palm-50 text-palm-700';
  } else if (lower === 'draft') {
    colorClasses = 'bg-cream-200 text-warm-gray-600';
  } else if (lower === 'archived') {
    colorClasses = 'bg-coral-50 text-coral-700';
  }

  return (
    <span className={`inline-flex items-center text-xs px-2 py-0.5 rounded-sm ${colorClasses}`}>
      {status}
    </span>
  );
}

// =============================================================================
// Connected State (Sidebar + Table)
// =============================================================================

function ConnectedPagesView({
  projectId,
  storeDomain,
  lastSyncAt,
  syncStatus,
}: {
  projectId: string;
  storeDomain: string;
  lastSyncAt?: string;
  syncStatus?: string;
}) {
  const [activeCategory, setActiveCategory] = useState<CategoryKey>('collection');
  const [currentPage, setCurrentPage] = useState(1);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  const syncMutation = useShopifySync(projectId);

  const { data: counts } = useShopifyPageCounts(projectId);
  const { data: pagesData, isLoading: pagesLoading } = useShopifyPages(
    projectId,
    activeCategory,
    currentPage,
    debouncedSearch
  );

  const categoryDef = CATEGORIES.find((c) => c.key === activeCategory)!;

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setCurrentPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Reset page and search when switching categories
  const handleCategoryChange = useCallback((key: CategoryKey) => {
    setActiveCategory(key);
    setCurrentPage(1);
    setSearch('');
    setDebouncedSearch('');
  }, []);

  const isSyncing = syncStatus === 'syncing' || syncMutation.isPending;

  // Extract store name from domain
  const storeName = storeDomain.replace('.myshopify.com', '');

  return (
    <div className="flex gap-6">
      {/* Sidebar */}
      <CategorySidebar
        activeCategory={activeCategory}
        onCategoryChange={handleCategoryChange}
        counts={counts}
      />

      {/* Content */}
      <div className="flex-1 min-w-0">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-warm-gray-900">
              {categoryDef.label}
              <span className="text-warm-gray-400 font-normal ml-2 text-base">
                {pagesData?.total ?? counts?.[activeCategory] ?? 0} {categoryDef.labelPlural}
              </span>
            </h3>
            <div className="flex items-center gap-2 text-sm text-warm-gray-500 mt-1">
              <span>Shopify &middot; {storeName}</span>
              {lastSyncAt && (
                <>
                  <span className="text-cream-400">&middot;</span>
                  <span>Synced {formatRelativeTime(lastSyncAt)}</span>
                </>
              )}
            </div>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => syncMutation.mutate()}
            disabled={isSyncing}
          >
            {isSyncing ? (
              <>
                <SpinnerIcon className="w-3.5 h-3.5 mr-1.5" />
                Syncing...
              </>
            ) : (
              <>
                <RefreshIcon className="w-3.5 h-3.5 mr-1.5" />
                Sync Now
              </>
            )}
          </Button>
        </div>

        {/* Search */}
        <div className="relative mb-4">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-warm-gray-400" />
          <input
            type="text"
            placeholder={categoryDef.searchPlaceholder}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="block w-full pl-10 pr-4 py-2.5 text-sm text-warm-gray-900 bg-white border border-cream-400 rounded-sm transition-colors placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:border-palm-400 focus:ring-palm-200 hover:border-cream-500"
          />
        </div>

        {/* Table */}
        {pagesLoading ? (
          <div className="flex items-center justify-center py-12">
            <SpinnerIcon className="w-6 h-6 text-palm-500" />
            <span className="ml-2 text-warm-gray-500 text-sm">Loading...</span>
          </div>
        ) : (
          <PagesTable
            pages={pagesData?.items ?? []}
            columns={categoryDef.columns}
            total={pagesData?.total ?? 0}
            currentPage={currentPage}
            perPage={25}
            onPageChange={setCurrentPage}
          />
        )}
      </div>
    </div>
  );
}

// =============================================================================
// PagesTab (entry point)
// =============================================================================

export function PagesTab({ projectId }: { projectId: string }) {
  const [pollInterval, setPollInterval] = useState<number | false>(false);
  const { data: status, isLoading } = useShopifyStatus(projectId, {
    refetchInterval: pollInterval,
  });

  // Enable polling while syncing
  useEffect(() => {
    setPollInterval(status?.sync_status === 'syncing' ? 2000 : false);
  }, [status?.sync_status]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <SpinnerIcon className="w-6 h-6 text-palm-500" />
        <span className="ml-2 text-warm-gray-500">Loading...</span>
      </div>
    );
  }

  // Not connected
  if (!status?.connected) {
    return <NotConnectedState projectId={projectId} />;
  }

  // First sync in progress
  if (status.sync_status === 'syncing') {
    return <SyncingState projectId={projectId} storeDomain={status.store_domain} />;
  }

  // Connected
  return (
    <ConnectedPagesView
      projectId={projectId}
      storeDomain={status.store_domain || ''}
      lastSyncAt={status.last_sync_at}
      syncStatus={status.sync_status}
    />
  );
}
