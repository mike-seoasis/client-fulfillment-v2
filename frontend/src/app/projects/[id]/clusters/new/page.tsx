'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useState, useCallback } from 'react';
import { useProject } from '@/hooks/use-projects';
import { useCreateCluster } from '@/hooks/useClusters';
import { Button, Input } from '@/components/ui';

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

const PROGRESS_STEPS = [
  'Generating suggestions...',
  'Checking search volume...',
  'Finalizing results...',
] as const;

function ProgressIndicator({ currentStep }: { currentStep: number }) {
  return (
    <div className="flex flex-col items-center py-8">
      <div className="mb-6">
        <div className="w-10 h-10 border-3 border-palm-500 border-t-transparent rounded-full animate-spin" />
      </div>
      <div className="space-y-3 w-full max-w-xs">
        {PROGRESS_STEPS.map((label, index) => (
          <div key={label} className="flex items-center gap-3">
            <div
              className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                index < currentStep
                  ? 'bg-palm-500'
                  : index === currentStep
                  ? 'bg-palm-500'
                  : 'bg-cream-300'
              }`}
            >
              {index < currentStep ? (
                <svg className="w-3 h-3 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              ) : index === currentStep ? (
                <div className="w-2 h-2 bg-white rounded-full" />
              ) : null}
            </div>
            <span
              className={`text-sm ${
                index <= currentStep ? 'text-warm-gray-900 font-medium' : 'text-warm-gray-400'
              }`}
            >
              {label}
            </span>
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
      <div className="h-8 bg-cream-300 rounded w-64 mb-6" />
      <div className="bg-white rounded-sm border border-cream-500 p-6">
        <div className="h-5 bg-cream-300 rounded w-32 mb-4" />
        <div className="h-10 bg-cream-300 rounded w-full mb-6" />
        <div className="h-5 bg-cream-300 rounded w-40 mb-4" />
        <div className="h-10 bg-cream-300 rounded w-full" />
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

export default function NewClusterPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [seedKeyword, setSeedKeyword] = useState('');
  const [clusterName, setClusterName] = useState('');
  const [seedKeywordError, setSeedKeywordError] = useState<string | null>(null);
  const [progressStep, setProgressStep] = useState(0);

  const { data: project, isLoading, error } = useProject(projectId);
  const createCluster = useCreateCluster();

  const validate = useCallback((): boolean => {
    if (seedKeyword.trim().length < 2) {
      setSeedKeywordError('Seed keyword must be at least 2 characters');
      return false;
    }
    setSeedKeywordError(null);
    return true;
  }, [seedKeyword]);

  const handleSubmit = useCallback(() => {
    if (!validate()) return;

    // Reset and start progress animation
    setProgressStep(0);

    // Advance progress steps on a timer to show activity during the ~5-10s API call
    const timer1 = setTimeout(() => setProgressStep(1), 3000);
    const timer2 = setTimeout(() => setProgressStep(2), 6000);

    createCluster.mutate(
      {
        projectId,
        data: {
          seed_keyword: seedKeyword.trim(),
          name: clusterName.trim() || undefined,
        },
      },
      {
        onSuccess: (data) => {
          clearTimeout(timer1);
          clearTimeout(timer2);
          router.push(`/projects/${projectId}/clusters/${data.id}`);
        },
        onError: () => {
          clearTimeout(timer1);
          clearTimeout(timer2);
        },
      }
    );
  }, [validate, seedKeyword, clusterName, projectId, createCluster, router]);

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
        <span className="mx-2">&rsaquo;</span>
        <span className="text-warm-gray-900">New Cluster</span>
      </nav>

      {/* Page title */}
      <h1 className="text-2xl font-semibold text-warm-gray-900 mb-6">
        Create New Keyword Cluster
      </h1>

      {/* Form card */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
        {createCluster.isPending ? (
          <ProgressIndicator currentStep={progressStep} />
        ) : createCluster.isError ? (
          <div>
            <div className="mb-6 p-4 bg-coral-50 border border-coral-200 rounded-sm">
              <p className="text-sm font-medium text-coral-800 mb-1">
                Something went wrong
              </p>
              <p className="text-sm text-coral-700">
                {createCluster.error?.message || 'An unexpected error occurred. Please try again.'}
              </p>
            </div>
            <div className="flex justify-end gap-3">
              <Link href={`/projects/${projectId}`}>
                <Button variant="secondary">Cancel</Button>
              </Link>
              <Button onClick={handleSubmit}>
                Try Again
              </Button>
            </div>
          </div>
        ) : (
          <div>
            <div className="space-y-5">
              <Input
                label="Seed Keyword"
                placeholder="e.g. trail running shoes"
                value={seedKeyword}
                onChange={(e) => {
                  setSeedKeyword(e.target.value);
                  if (seedKeywordError) setSeedKeywordError(null);
                }}
                error={seedKeywordError || undefined}
                required
                autoFocus
              />
              <div>
                <Input
                  label="Cluster Name (optional)"
                  placeholder="Defaults to seed keyword if left blank"
                  value={clusterName}
                  onChange={(e) => setClusterName(e.target.value)}
                />
                <p className="mt-1.5 text-xs text-warm-gray-500">
                  Defaults to seed keyword if left blank
                </p>
              </div>
            </div>

            <hr className="border-cream-300 my-6" />

            <div className="flex justify-end gap-3">
              <Link href={`/projects/${projectId}`}>
                <Button variant="secondary">Cancel</Button>
              </Link>
              <Button
                onClick={handleSubmit}
                disabled={seedKeyword.trim().length < 2}
              >
                Get Suggestions
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
