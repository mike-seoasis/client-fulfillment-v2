'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import { useContentGenerationStatus } from '@/hooks/useContentGeneration';
import { exportProject } from '@/lib/api';
import { Button, Toast } from '@/components/ui';
import type { PageGenerationStatusItem } from '@/lib/api';

// Step indicator data - shared across onboarding pages
const ONBOARDING_STEPS = [
  { key: 'upload', label: 'Upload' },
  { key: 'crawl', label: 'Crawl' },
  { key: 'keywords', label: 'Keywords' },
  { key: 'content', label: 'Content' },
  { key: 'export', label: 'Export' },
] as const;

function BackArrowIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function XCircleIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" opacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" className="animate-spin origin-center" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function StepIndicator({ currentStep }: { currentStep: string }) {
  const currentIndex = ONBOARDING_STEPS.findIndex((s) => s.key === currentStep);

  return (
    <div className="mb-8">
      <p className="text-sm text-warm-gray-600 mb-3">
        Step {currentIndex + 1} of {ONBOARDING_STEPS.length}: {ONBOARDING_STEPS[currentIndex].label}
      </p>
      <div className="flex items-center gap-1">
        {ONBOARDING_STEPS.map((step, index) => (
          <div key={step.key} className="flex items-center">
            <div
              className={`w-3 h-3 rounded-full ${
                index < currentIndex
                  ? 'bg-palm-500'
                  : index === currentIndex
                  ? 'bg-palm-500'
                  : 'bg-cream-300'
              }`}
            />
            {index < ONBOARDING_STEPS.length - 1 && (
              <div
                className={`w-12 h-0.5 ${
                  index < currentIndex ? 'bg-palm-500' : 'bg-cream-300'
                }`}
              />
            )}
          </div>
        ))}
      </div>
      <div className="flex mt-1">
        {ONBOARDING_STEPS.map((step, index) => (
          <div
            key={step.key}
            className={`text-xs ${
              index === 0 ? 'text-left' : index === ONBOARDING_STEPS.length - 1 ? 'text-right' : 'text-center'
            } ${
              index <= currentIndex ? 'text-palm-700' : 'text-warm-gray-400'
            }`}
            style={{ width: index === ONBOARDING_STEPS.length - 1 ? 'auto' : '60px' }}
          >
            {step.label}
          </div>
        ))}
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-4 bg-cream-300 rounded w-48 mb-6" />
      <div className="mb-8">
        <div className="h-4 bg-cream-300 rounded w-32 mb-3" />
        <div className="flex items-center gap-1">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center">
              <div className="w-3 h-3 rounded-full bg-cream-300" />
              {i < 4 && <div className="w-12 h-0.5 bg-cream-300" />}
            </div>
          ))}
        </div>
      </div>
      <div className="bg-white rounded-sm border border-cream-500 p-6">
        <div className="h-6 bg-cream-300 rounded w-48 mb-4" />
        <div className="h-4 bg-cream-300 rounded w-full mb-6" />
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-12 bg-cream-300 rounded w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}

function NotFoundState() {
  return (
    <div className="text-center py-12">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-coral-50 mb-4">
        <XCircleIcon className="w-8 h-8 text-coral-500" />
      </div>
      <h1 className="text-2xl font-semibold text-warm-gray-900 mb-2">
        Project Not Found
      </h1>
      <p className="text-warm-gray-600 mb-6">
        The project you&apos;re looking for doesn&apos;t exist or has been deleted.
      </p>
      <Link href="/">
        <Button>Back to Dashboard</Button>
      </Link>
    </div>
  );
}

/** Extract display path from URL */
function displayPath(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.pathname + parsed.search;
  } catch {
    return url;
  }
}

export default function ExportPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const { data: status, isLoading: isStatusLoading } = useContentGenerationStatus(projectId);

  // Page selection state
  const [selectedPageIds, setSelectedPageIds] = useState<Set<string>>(new Set());
  const [initialized, setInitialized] = useState(false);

  // Export state
  const [isExporting, setIsExporting] = useState(false);

  // Toast state
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');

  const isLoading = isProjectLoading || isStatusLoading;

  // Get approved pages
  const approvedPages: PageGenerationStatusItem[] = status
    ? status.pages.filter((p) => p.status === 'complete' && p.is_approved)
    : [];

  // Initialize selection to all approved pages once data loads
  if (!initialized && approvedPages.length > 0) {
    setSelectedPageIds(new Set(approvedPages.map((p) => p.page_id)));
    setInitialized(true);
  }

  const togglePage = (pageId: string) => {
    setSelectedPageIds((prev) => {
      const next = new Set(prev);
      if (next.has(pageId)) {
        next.delete(pageId);
      } else {
        next.add(pageId);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedPageIds.size === approvedPages.length) {
      setSelectedPageIds(new Set());
    } else {
      setSelectedPageIds(new Set(approvedPages.map((p) => p.page_id)));
    }
  };

  const handleExport = async () => {
    if (selectedPageIds.size === 0) return;
    setIsExporting(true);
    try {
      await exportProject(projectId, Array.from(selectedPageIds));
      setToastMessage('Export downloaded successfully');
      setToastVariant('success');
      setShowToast(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to export';
      setToastMessage(message);
      setToastVariant('error');
      setShowToast(true);
    } finally {
      setIsExporting(false);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div>
        <Link
          href="/"
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          All Projects
        </Link>
        <LoadingSkeleton />
      </div>
    );
  }

  // 404 state
  if (projectError || !project) {
    return (
      <div>
        <Link
          href="/"
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          All Projects
        </Link>
        <NotFoundState />
      </div>
    );
  }

  const allSelected = approvedPages.length > 0 && selectedPageIds.size === approvedPages.length;
  const someSelected = selectedPageIds.size > 0 && selectedPageIds.size < approvedPages.length;

  return (
    <div>
      {/* Breadcrumb navigation */}
      <nav className="flex items-center text-sm text-warm-gray-600 mb-6">
        <Link href={`/projects/${projectId}`} className="hover:text-warm-gray-900 flex items-center">
          <BackArrowIcon className="w-4 h-4 mr-1" />
          {project.name}
        </Link>
        <span className="mx-2">&rsaquo;</span>
        <span className="text-warm-gray-900">Onboarding</span>
      </nav>

      {/* Step indicator */}
      <StepIndicator currentStep="export" />

      {/* Divider */}
      <hr className="border-cream-500 mb-6" />

      {/* Page content */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-warm-gray-900 mb-1">
          Export content for Matrixify import
        </h2>
        <p className="text-sm text-warm-gray-600 mb-6">
          Select the pages to include in your CSV export. Only approved pages are available.
        </p>

        {approvedPages.length === 0 ? (
          <div className="text-center py-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-cream-100 mb-4">
              <XCircleIcon className="w-8 h-8 text-warm-gray-400" />
            </div>
            <h3 className="text-lg font-medium text-warm-gray-900 mb-1">No Approved Pages</h3>
            <p className="text-warm-gray-600 text-sm">
              Approve content in the previous step before exporting.
            </p>
          </div>
        ) : (
          <>
            {/* Summary */}
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm text-warm-gray-700">
                Ready to export: <span className="font-semibold text-warm-gray-900">{selectedPageIds.size} page{selectedPageIds.size !== 1 ? 's' : ''}</span>
              </p>
            </div>

            {/* Export includes */}
            <div className="mb-4 p-3 bg-cream-50 rounded-sm border border-cream-300 text-sm text-warm-gray-700">
              <p className="font-medium text-warm-gray-900 mb-1">Export includes:</p>
              <ul className="list-disc list-inside space-y-0.5 text-warm-gray-600">
                <li>Handle (URL slug)</li>
                <li>Title</li>
                <li>Body HTML</li>
                <li>Meta description</li>
              </ul>
            </div>

            {/* Page selection list */}
            <div className="border border-cream-500 rounded-sm overflow-hidden mb-6">
              {/* Select all header */}
              <div className="flex items-center gap-3 px-4 py-2.5 bg-cream-100 border-b border-cream-500">
                <input
                  type="checkbox"
                  checked={allSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = someSelected;
                  }}
                  onChange={toggleAll}
                  className="rounded-sm border-sand-500 text-palm-500 focus:ring-palm-400"
                />
                <span className="text-xs font-medium text-warm-gray-600 uppercase tracking-wide">
                  {allSelected ? 'Deselect All' : 'Select All'} ({approvedPages.length} page{approvedPages.length !== 1 ? 's' : ''})
                </span>
              </div>

              {/* Page rows */}
              <div className="max-h-[24rem] overflow-y-auto divide-y divide-cream-300">
                {approvedPages.map((page) => (
                  <label
                    key={page.page_id}
                    className="flex items-center gap-3 px-4 py-3 hover:bg-cream-50 transition-colors cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedPageIds.has(page.page_id)}
                      onChange={() => togglePage(page.page_id)}
                      className="rounded-sm border-sand-500 text-palm-500 focus:ring-palm-400"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-warm-gray-900 truncate" title={page.url}>
                        {displayPath(page.url)}
                      </p>
                      <p className="text-xs text-warm-gray-500 mt-0.5">
                        Keyword: <span className="font-medium text-warm-gray-700">{page.keyword}</span>
                      </p>
                    </div>
                    <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-sm bg-palm-100 text-palm-700 shrink-0">
                      <CheckIcon className="w-3 h-3" />
                      Approved
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* Format note */}
            <p className="text-xs text-warm-gray-500 mb-4">
              Format: CSV (UTF-8) &mdash; Matrixify compatible
            </p>

            {/* Download button */}
            <div className="flex justify-center">
              <Button
                onClick={handleExport}
                disabled={selectedPageIds.size === 0 || isExporting}
              >
                {isExporting ? (
                  <>
                    <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                    Exporting...
                  </>
                ) : (
                  <>
                    <DownloadIcon className="w-4 h-4 mr-1.5" />
                    Download Export
                  </>
                )}
              </Button>
            </div>
          </>
        )}

        <hr className="border-cream-500 my-6" />

        {/* Navigation */}
        <div className="flex justify-end gap-3">
          <Link href={`/projects/${projectId}/onboarding/content`}>
            <Button variant="secondary">Back</Button>
          </Link>
          <Link href={`/projects/${projectId}`}>
            <Button>Finish Onboarding</Button>
          </Link>
        </div>
      </div>

      {/* Toast */}
      {showToast && (
        <Toast
          message={toastMessage}
          variant={toastVariant}
          onClose={() => setShowToast(false)}
        />
      )}
    </div>
  );
}
