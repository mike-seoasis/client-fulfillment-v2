'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState, useMemo } from 'react';
import { useProject } from '@/hooks/use-projects';
import { Button } from '@/components/ui';
import { UrlUploader, type ParsedUrl, isValidUrl, normalizeUrl } from '@/components/onboarding/UrlUploader';
import { CsvDropzone, type CsvParseResult } from '@/components/onboarding/CsvDropzone';

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

  const { data: project, isLoading, error } = useProject(projectId);

  // Combine URLs from textarea and CSV, deduplicating by normalized URL
  const parsedUrls = useMemo(() => {
    const combined: ParsedUrl[] = [...textareaUrls];
    const existingUrls = new Set(textareaUrls.map((u) => u.normalizedUrl));

    for (const url of csvResult.urls) {
      const valid = isValidUrl(url);
      const normalized = valid ? normalizeUrl(url) : url.toLowerCase();

      if (!existingUrls.has(normalized)) {
        combined.push({
          url,
          normalizedUrl: normalized,
          isValid: valid,
        });
        existingUrls.add(normalized);
      }
    }

    return combined;
  }, [textareaUrls, csvResult.urls]);

  const validUrls = parsedUrls.filter((u) => u.isValid);
  const invalidUrls = parsedUrls.filter((u) => !u.isValid);

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

        {/* URL count summary */}
        <div className="text-warm-gray-500 text-sm mb-4">
          URLs to process:{' '}
          <span className="font-medium text-warm-gray-700">{validUrls.length}</span>
          {invalidUrls.length > 0 && (
            <span className="text-coral-500 ml-2">
              ({invalidUrls.length} invalid)
            </span>
          )}
        </div>

        {/* URL preview list */}
        {parsedUrls.length === 0 ? (
          <div className="text-center py-8 text-warm-gray-400 text-sm">
            Enter URLs above to see them listed here
          </div>
        ) : (
          <div className="max-h-48 overflow-y-auto border border-cream-300 rounded-sm">
            {parsedUrls.map((item, index) => (
              <div
                key={index}
                className={`px-3 py-2 text-sm font-mono border-b border-cream-200 last:border-b-0 ${
                  item.isValid
                    ? 'text-warm-gray-700 bg-white'
                    : 'text-coral-600 bg-coral-50'
                }`}
              >
                {item.url}
                {!item.isValid && (
                  <span className="ml-2 text-xs text-coral-500">(invalid URL)</span>
                )}
              </div>
            ))}
          </div>
        )}

        <hr className="border-cream-300 my-6" />

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Link href={`/projects/${projectId}`}>
            <Button variant="secondary">Cancel</Button>
          </Link>
          <Button disabled={validUrls.length === 0}>Start Crawl</Button>
        </div>
      </div>
    </div>
  );
}
