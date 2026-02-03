'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import { useBrandConfig, useRegenerateBrandConfig } from '@/hooks/useBrandConfig';
import { Button } from '@/components/ui';

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      {/* Back link skeleton */}
      <div className="h-4 bg-cream-300 rounded w-32 mb-6" />

      {/* Header skeleton */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="h-7 bg-cream-300 rounded w-48 mb-2" />
          <div className="h-4 bg-cream-300 rounded w-64" />
        </div>
        <div className="h-10 bg-cream-300 rounded w-32" />
      </div>

      {/* Content area skeleton */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 min-h-[400px]">
        <div className="h-6 bg-cream-300 rounded w-40 mb-4" />
        <div className="space-y-3">
          <div className="h-4 bg-cream-300 rounded w-full" />
          <div className="h-4 bg-cream-300 rounded w-3/4" />
          <div className="h-4 bg-cream-300 rounded w-5/6" />
        </div>
      </div>
    </div>
  );
}

function NotFoundState({ type }: { type: 'project' | 'brand-config' }) {
  const isProject = type === 'project';

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
        {isProject ? 'Project Not Found' : 'Brand Configuration Not Found'}
      </h1>
      <p className="text-warm-gray-600 mb-6">
        {isProject
          ? "The project you're looking for doesn't exist or has been deleted."
          : 'This project doesn\'t have a brand configuration yet. Generate one from the project creation flow.'}
      </p>
      <Link href={isProject ? '/' : `/projects`}>
        <Button>{isProject ? 'Back to Dashboard' : 'Back to Projects'}</Button>
      </Link>
    </div>
  );
}

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

function RefreshIcon({ className }: { className?: string }) {
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
      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
      <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
      <path d="M21 21v-5h-5" />
    </svg>
  );
}

export default function BrandConfigPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const { data: brandConfig, isLoading: isBrandConfigLoading, error: brandConfigError } = useBrandConfig(projectId);
  const regenerateMutation = useRegenerateBrandConfig(projectId);

  const isLoading = isProjectLoading || isBrandConfigLoading;

  const handleRegenerateAll = () => {
    regenerateMutation.mutate(undefined);
  };

  // Loading state
  if (isLoading) {
    return (
      <div>
        <Link
          href={`/projects/${projectId}`}
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          Back to Project
        </Link>
        <LoadingSkeleton />
      </div>
    );
  }

  // Project not found
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
        <NotFoundState type="project" />
      </div>
    );
  }

  // Brand config not found (404 from API)
  if (brandConfigError || !brandConfig) {
    return (
      <div>
        <Link
          href={`/projects/${projectId}`}
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          Back to Project
        </Link>
        <NotFoundState type="brand-config" />
      </div>
    );
  }

  return (
    <div>
      {/* Back link */}
      <Link
        href={`/projects/${projectId}`}
        className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
      >
        <BackArrowIcon className="w-4 h-4 mr-1" />
        Back to Project
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-warm-gray-900 mb-1">
            Brand Configuration
          </h1>
          <p className="text-warm-gray-500 text-sm">
            {project.name}
          </p>
        </div>
        <Button
          onClick={handleRegenerateAll}
          disabled={regenerateMutation.isPending}
          variant="secondary"
        >
          <RefreshIcon className={`w-4 h-4 mr-2 ${regenerateMutation.isPending ? 'animate-spin' : ''}`} />
          {regenerateMutation.isPending ? 'Regenerating...' : 'Regenerate All'}
        </Button>
      </div>

      {/* Divider */}
      <hr className="border-cream-500 mb-6" />

      {/* Content placeholder - section navigation and content will be added in subsequent stories */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm min-h-[400px]">
        <p className="text-warm-gray-500 text-sm">
          Brand configuration sections will appear here.
        </p>
      </div>
    </div>
  );
}
