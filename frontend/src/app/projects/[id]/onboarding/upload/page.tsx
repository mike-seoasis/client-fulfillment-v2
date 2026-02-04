'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState, useMemo, useCallback } from 'react';
import { useProject } from '@/hooks/use-projects';
import { Button } from '@/components/ui';
import { UrlUploader, type ParsedUrl, isValidUrl, normalizeUrl, getDomain } from '@/components/onboarding/UrlUploader';
import { CsvDropzone, type CsvParseResult } from '@/components/onboarding/CsvDropzone';
import { UrlPreviewList } from '@/components/onboarding/UrlPreviewList';

// Step indicator data
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

function WarningIcon({ className }: { className?: string }) {
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
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
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
            {/* Step circle */}
            <div
              className={`w-3 h-3 rounded-full ${
                index < currentIndex
                  ? 'bg-palm-500'
                  : index === currentIndex
                  ? 'bg-palm-500'
                  : 'bg-cream-300'
              }`}
            />
            {/* Connector line */}
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
      {/* Breadcrumb skeleton */}
      <div className="h-4 bg-cream-300 rounded w-48 mb-6" />

      {/* Step indicator skeleton */}
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

      {/* Content skeleton */}
      <div className="bg-white rounded-sm border border-cream-500 p-6">
        <div className="h-6 bg-cream-300 rounded w-64 mb-4" />
        <div className="h-32 bg-cream-300 rounded w-full mb-4" />
        <div className="h-10 bg-cream-300 rounded w-32" />
      </div>
    </div>
  );
}

function NotFoundState() {
  return (
    <div className="text-center py-12">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-coral-50 mb-4">
        <svg
          className="w-8 h-8 text-coral-500"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
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

export default function UrlUploadPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [textareaUrls, setTextareaUrls] = useState<ParsedUrl[]>([]);
  const [csvResult, setCsvResult] = useState<CsvParseResult>({
    urls: [],
    error: null,
    filename: null,
  });
  // Track manually removed URLs by their normalized URL
  const [removedUrls, setRemovedUrls] = useState<Set<string>>(new Set());

  const { data: project, isLoading, error } = useProject(projectId);

  // Combine URLs from textarea and CSV, deduplicating by normalized URL
  // and filtering out manually removed URLs
  const parsedUrls = useMemo(() => {
    const combined: ParsedUrl[] = [];
    const existingUrls = new Set<string>();

    // Add textarea URLs (filtering out removed ones)
    for (const item of textareaUrls) {
      if (!removedUrls.has(item.normalizedUrl) && !existingUrls.has(item.normalizedUrl)) {
        combined.push(item);
        existingUrls.add(item.normalizedUrl);
      }
    }

    // Add CSV URLs (filtering out removed ones and duplicates)
    for (const url of csvResult.urls) {
      const valid = isValidUrl(url);
      const normalized = valid ? normalizeUrl(url) : url.toLowerCase();

      if (!removedUrls.has(normalized) && !existingUrls.has(normalized)) {
        combined.push({
          url,
          normalizedUrl: normalized,
          isValid: valid,
        });
        existingUrls.add(normalized);
      }
    }

    return combined;
  }, [textareaUrls, csvResult.urls, removedUrls]);

  // Handle removing a URL from the preview list
  const handleRemoveUrl = useCallback((normalizedUrl: string) => {
    setRemovedUrls((prev) => {
      const next = new Set(prev);
      next.add(normalizedUrl);
      return next;
    });
  }, []);

  const validUrlCount = parsedUrls.filter((u) => u.isValid).length;

  // Check if any valid URLs are from a different domain than the project's site_url
  const hasDifferentDomainUrls = useMemo(() => {
    if (!project) return false;

    const projectDomain = getDomain(project.site_url);
    if (!projectDomain) return false;

    return parsedUrls.some((item) => {
      if (!item.isValid) return false;
      const urlDomain = getDomain(item.url);
      return urlDomain && urlDomain !== projectDomain;
    });
  }, [parsedUrls, project]);

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
  if (error || !project) {
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

  return (
    <div>
      {/* Breadcrumb navigation */}
      <nav className="flex items-center text-sm text-warm-gray-600 mb-6">
        <Link href={`/projects/${projectId}`} className="hover:text-warm-gray-900 flex items-center">
          <BackArrowIcon className="w-4 h-4 mr-1" />
          {project.name}
        </Link>
        <span className="mx-2">›</span>
        <span className="text-warm-gray-900">Onboarding</span>
      </nav>

      {/* Step indicator */}
      <StepIndicator currentStep="upload" />

      {/* Divider */}
      <hr className="border-cream-500 mb-6" />

      {/* Page content */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-warm-gray-900 mb-4">
          Paste your collection page URLs (one per line)
        </h2>

        <UrlUploader
          onChange={setTextareaUrls}
          placeholder={`https://${project.site_url.replace(/^https?:\/\//, '')}/collections/example-collection\nhttps://${project.site_url.replace(/^https?:\/\//, '')}/collections/another-collection`}
        />

        <div className="mt-6">
          <h3 className="text-sm font-medium text-warm-gray-700 mb-2">
            Or upload a CSV file
          </h3>
          <CsvDropzone onParsed={setCsvResult} />
          {csvResult.error && (
            <p className="mt-2 text-sm text-coral-600">{csvResult.error}</p>
          )}
          {csvResult.filename && !csvResult.error && (
            <p className="mt-2 text-sm text-warm-gray-500">
              Loaded {csvResult.urls.length} URLs from{' '}
              <span className="font-medium">{csvResult.filename}</span>
            </p>
          )}
        </div>

        <hr className="border-cream-300 my-6" />

        {/* Domain warning banner */}
        {hasDifferentDomainUrls && (
          <div className="mb-4 p-3 bg-coral-50 border border-coral-200 rounded-sm flex items-start gap-2">
            <WarningIcon className="w-5 h-5 text-coral-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-coral-700">
              Some URLs are from a different domain
            </p>
          </div>
        )}

        {/* URL preview list with remove functionality */}
        <UrlPreviewList urls={parsedUrls} onRemove={handleRemoveUrl} />

        <hr className="border-cream-300 my-6" />

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Link href={`/projects/${projectId}`}>
            <Button variant="secondary">Cancel</Button>
          </Link>
          <Button disabled={validUrlCount === 0}>Start Crawl</Button>
        </div>
      </div>
    </div>
  );
}
