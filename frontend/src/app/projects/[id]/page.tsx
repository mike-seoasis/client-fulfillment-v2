'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useProject, useDeleteProject } from '@/hooks/use-projects';
import { Button, Toast } from '@/components/ui';

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      {/* Back link skeleton */}
      <div className="h-4 bg-cream-300 rounded w-24 mb-6" />

      {/* Header skeleton */}
      <div className="mb-8">
        <div className="h-8 bg-cream-300 rounded w-48 mb-2" />
        <div className="h-4 bg-cream-300 rounded w-64" />
      </div>

      {/* Sections skeleton */}
      <div className="space-y-6">
        <div className="bg-white rounded-sm border border-cream-500 p-6">
          <div className="h-6 bg-cream-300 rounded w-40 mb-4" />
          <div className="h-4 bg-cream-300 rounded w-full mb-2" />
          <div className="h-10 bg-cream-300 rounded w-32" />
        </div>
        <div className="bg-white rounded-sm border border-cream-500 p-6">
          <div className="h-6 bg-cream-300 rounded w-32 mb-4" />
          <div className="h-4 bg-cream-300 rounded w-3/4" />
        </div>
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

function ClipboardIcon({ className }: { className?: string }) {
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
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
    </svg>
  );
}

function PlusIcon({ className }: { className?: string }) {
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
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const { data: project, isLoading, error } = useProject(projectId);
  const deleteProject = useDeleteProject();

  // Two-step delete confirmation
  const [isConfirming, setIsConfirming] = useState(false);
  const [showToast, setShowToast] = useState(false);
  const confirmTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const deleteButtonRef = useRef<HTMLButtonElement>(null);

  // Reset confirmation state after 3 seconds
  useEffect(() => {
    if (isConfirming) {
      confirmTimeoutRef.current = setTimeout(() => {
        setIsConfirming(false);
      }, 3000);
    }
    return () => {
      if (confirmTimeoutRef.current) {
        clearTimeout(confirmTimeoutRef.current);
      }
    };
  }, [isConfirming]);

  // Handle blur to reset confirmation
  const handleBlur = useCallback((e: React.FocusEvent) => {
    // Only reset if focus is moving outside the button
    if (!deleteButtonRef.current?.contains(e.relatedTarget as Node)) {
      setIsConfirming(false);
    }
  }, []);

  const handleDeleteClick = async () => {
    if (!isConfirming) {
      // First click: show confirmation state
      setIsConfirming(true);
      return;
    }

    // Second click: execute deletion
    try {
      await deleteProject.mutateAsync(projectId);
      setShowToast(true);
      // Delay redirect slightly to show toast
      setTimeout(() => {
        router.push('/');
      }, 500);
    } catch {
      // Error is already handled by optimistic update rollback
      setIsConfirming(false);
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
          <svg
            className="w-4 h-4 mr-1"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
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
          <svg
            className="w-4 h-4 mr-1"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          All Projects
        </Link>
        <NotFoundState />
      </div>
    );
  }

  return (
    <div>
      {/* Back link */}
      <Link
        href="/"
        className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
      >
        <svg
          className="w-4 h-4 mr-1"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        All Projects
      </Link>

      {/* Project header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-warm-gray-900 mb-1">
            {project.name}
          </h1>
          <a
            href={project.site_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-warm-gray-500 hover:text-palm-600 text-sm"
          >
            {project.site_url}
          </a>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative group">
            <Button variant="secondary" disabled>
              Edit Brand
            </Button>
            {/* Tooltip */}
            <div className="absolute right-0 top-full mt-2 px-3 py-1.5 bg-warm-gray-900 text-white text-xs rounded-sm opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
              Coming in Phase 2
            </div>
          </div>
          <Button
            ref={deleteButtonRef}
            variant="danger"
            onClick={handleDeleteClick}
            onBlur={handleBlur}
            disabled={deleteProject.isPending}
          >
            {deleteProject.isPending
              ? 'Deleting...'
              : isConfirming
              ? 'Confirm Delete'
              : 'Delete Project'}
          </Button>
        </div>
      </div>

      {/* Toast notification */}
      {showToast && (
        <Toast
          message="Project deleted"
          variant="success"
          onClose={() => setShowToast(false)}
        />
      )}

      {/* Divider */}
      <hr className="border-cream-500 mb-8" />

      {/* Sections */}
      <div className="space-y-6">
        {/* Onboarding section */}
        <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <ClipboardIcon className="w-5 h-5 text-palm-500" />
            <h2 className="text-lg font-semibold text-warm-gray-900">
              Onboarding
            </h2>
            <span className="text-xs bg-cream-100 text-warm-gray-600 px-2 py-0.5 rounded-full">
              Existing Pages
            </span>
          </div>
          <p className="text-warm-gray-600 text-sm mb-4">
            Optimize existing collection pages with new copy
          </p>
          <Button disabled>Continue</Button>
        </div>

        {/* New Content section */}
        <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <PlusIcon className="w-5 h-5 text-palm-500" />
            <h2 className="text-lg font-semibold text-warm-gray-900">
              New Content
            </h2>
            <span className="text-xs bg-cream-100 text-warm-gray-600 px-2 py-0.5 rounded-full">
              Keyword Clusters
            </span>
          </div>
          <p className="text-warm-gray-600 text-sm mb-4">
            Build new collection pages from keyword clusters
          </p>
          <Button disabled>+ New Cluster</Button>
        </div>
      </div>
    </div>
  );
}
