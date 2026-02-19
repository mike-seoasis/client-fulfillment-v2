'use client';

import { Suspense, useCallback, useEffect, useId, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { ProjectForm, type ProjectFormData } from '@/components/ProjectForm';
import { type UploadedFile } from '@/components/FileUpload';
import { GenerationProgress } from '@/components/GenerationProgress';
import { useCreateProject, useProject } from '@/hooks/use-projects';
import { uploadFileToProject } from '@/hooks/useProjectFiles';
import {
  useStartBrandConfigGeneration,
  useBrandConfigStatus,
} from '@/hooks/useBrandConfigGeneration';
import { useUpsertRedditConfig } from '@/hooks/useReddit';
import { upsertRedditConfig } from '@/lib/api';
import { Button } from '@/components/ui';

type WizardStep = 1 | 2;

export default function CreateProjectPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-xl mx-auto">
          <div className="bg-white rounded-sm border border-cream-500 p-8 shadow-sm">
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin w-6 h-6 border-2 border-palm-500 border-t-transparent rounded-full" />
              <span className="ml-3 text-warm-gray-600">Loading...</span>
            </div>
          </div>
        </div>
      }
    >
      <CreateProjectPageContent />
    </Suspense>
  );
}

function CreateProjectPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const createProject = useCreateProject();
  const [error, setError] = useState<string | null>(null);

  // Detect Reddit flow
  const isRedditFlow = searchParams.get('flow') === 'reddit';

  // Get project ID from URL if resuming
  const urlProjectId = searchParams.get('project');
  const [projectId, setProjectId] = useState<string | null>(urlProjectId);

  // Determine initial step based on URL
  const [currentStep, setCurrentStep] = useState<WizardStep>(
    urlProjectId ? 2 : 1
  );

  // File upload state
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const fileIdCounter = useRef(0);

  // Form ID for external submission
  const formId = useId();
  const [formData, setFormData] = useState<ProjectFormData | null>(null);

  // Brand config generation mutation
  const startGeneration = useStartBrandConfigGeneration();

  // Reddit config upsert (for reddit flow)
  const upsertRedditConfig = useUpsertRedditConfig(projectId ?? '');

  // Check generation status if resuming with a project ID
  const { data: statusData, isLoading: isCheckingStatus } = useBrandConfigStatus(
    urlProjectId ?? '',
    { enabled: !!urlProjectId }
  );

  // Fetch project details if resuming (for the project name)
  const { data: projectData } = useProject(urlProjectId ?? '', {
    enabled: !!urlProjectId,
  });

  // Track if files are being uploaded
  const [isUploadingFiles, setIsUploadingFiles] = useState(false);

  // Handle resume logic - if we have a URL project ID, check its status
  useEffect(() => {
    if (urlProjectId && statusData && !isCheckingStatus) {
      if (statusData.status === 'complete') {
        // Generation already complete, redirect to project
        router.push(isRedditFlow ? `/reddit/${urlProjectId}` : `/projects/${urlProjectId}`);
      } else if (statusData.status === 'generating') {
        // Still generating, stay on step 2
        setCurrentStep(2);
        setProjectId(urlProjectId);
      } else if (statusData.status === 'failed') {
        // Failed, show step 2 so user can see error and retry
        setCurrentStep(2);
        setProjectId(urlProjectId);
      } else if (statusData.status === 'pending') {
        // Never started, stay on step 2 to start
        setCurrentStep(2);
        setProjectId(urlProjectId);
      }
    }
  }, [urlProjectId, statusData, isCheckingStatus, router]);

  // Update URL when project ID changes
  const updateUrlWithProject = useCallback(
    (newProjectId: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set('project', newProjectId);
      router.replace(`/projects/new?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  // Handle file selection - add to pending list
  const handleFilesSelected = useCallback((files: File[]) => {
    const newUploadedFiles: UploadedFile[] = files.map((file) => ({
      id: `temp-${fileIdCounter.current++}`,
      name: file.name,
      size: file.size,
      progress: 0,
      status: 'pending' as const,
    }));

    setPendingFiles((prev) => [...prev, ...files]);
    setUploadedFiles((prev) => [...prev, ...newUploadedFiles]);
  }, []);

  // Handle file removal from the list
  const handleFileRemove = useCallback((fileId: string) => {
    setUploadedFiles((prev) => {
      const index = prev.findIndex((f) => f.id === fileId);
      if (index !== -1) {
        // Also remove from pending files by same index if it's a temp ID
        if (fileId.startsWith('temp-')) {
          const tempIndex = parseInt(fileId.replace('temp-', ''), 10);
          setPendingFiles((pendingPrev) =>
            pendingPrev.filter((_, i) => i !== tempIndex)
          );
        }
      }
      return prev.filter((f) => f.id !== fileId);
    });
  }, []);

  // Upload all pending files after project creation
  const uploadPendingFiles = useCallback(
    async (newProjectId: string) => {
      setIsUploadingFiles(true);
      try {
        for (let i = 0; i < pendingFiles.length; i++) {
          const file = pendingFiles[i];
          const uploadedFile = uploadedFiles[i];

          if (!uploadedFile || uploadedFile.status !== 'pending') continue;

          // Update status to uploading
          setUploadedFiles((prev) =>
            prev.map((f, idx) =>
              idx === i ? { ...f, status: 'uploading' as const, progress: 0 } : f
            )
          );

          try {
            await uploadFileToProject(newProjectId, file);

            // Mark as complete
            setUploadedFiles((prev) =>
              prev.map((f, idx) =>
                idx === i
                  ? { ...f, status: 'complete' as const, progress: 100 }
                  : f
              )
            );
          } catch (err) {
            // Mark as error
            setUploadedFiles((prev) =>
              prev.map((f, idx) =>
                idx === i
                  ? {
                      ...f,
                      status: 'error' as const,
                      error:
                        err instanceof Error ? err.message : 'Upload failed',
                    }
                  : f
              )
            );
          }
        }
      } finally {
        setIsUploadingFiles(false);
      }
    },
    [pendingFiles, uploadedFiles]
  );

  // Handle form submission (Step 1 -> Step 2)
  async function handleSubmit(data: ProjectFormData) {
    setError(null);
    setFormData(data);

    try {
      // Create the project
      const project = await createProject.mutateAsync({
        ...data,
        ...(isRedditFlow && { reddit_only: true }),
      });
      setProjectId(project.id);

      // Update URL with project ID (so refresh works)
      updateUrlWithProject(project.id);

      // For Reddit flow, create RedditProjectConfig before generation
      // so subreddit research can populate target_subreddits
      if (isRedditFlow) {
        try {
          await upsertRedditConfig(project.id, {});
        } catch {
          // Non-fatal — config can be created later
        }
      }

      // Upload any pending files
      if (pendingFiles.length > 0) {
        await uploadPendingFiles(project.id);
      }

      // Move to step 2 and start generation
      setCurrentStep(2);

      // Start brand config generation
      await startGeneration.mutateAsync(project.id);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to create project. Please try again.'
      );
    }
  }

  // Handle back button (Step 2 -> Step 1)
  // Note: This clears the URL param and resets state - useful if user wants to start fresh
  function handleBack() {
    // Clear URL params, preserve flow
    router.replace(isRedditFlow ? '/projects/new?flow=reddit' : '/projects/new', { scroll: false });
    setCurrentStep(1);
    setProjectId(null);
  }

  // Handle completion - go to project page (or Reddit detail in Reddit flow)
  function handleGoToProject() {
    if (projectId) {
      if (isRedditFlow) {
        // Auto-create Reddit config with defaults, then navigate
        upsertRedditConfig.mutate({}, {
          onSuccess: () => router.push(`/reddit/${projectId}`),
          onError: () => router.push(`/reddit/${projectId}`), // Navigate even if config fails
        });
      } else {
        router.push(`/projects/${projectId}`);
      }
    }
  }

  // Handle retry - restart generation
  async function handleRetry() {
    if (projectId) {
      await startGeneration.mutateAsync(projectId);
    }
  }

  const isSubmitting =
    createProject.isPending ||
    isUploadingFiles ||
    startGeneration.isPending;

  const backHref = isRedditFlow ? '/reddit' : '/';
  const backLabel = isRedditFlow ? 'Reddit Projects' : 'Back to Dashboard';
  const wizardTitle = isRedditFlow ? 'Create Reddit Project' : 'Create New Project';

  // Show loading state while checking status on resume
  if (urlProjectId && isCheckingStatus) {
    return (
      <div>
        <Link
          href={backHref}
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
          {backLabel}
        </Link>

        <div className="max-w-xl mx-auto">
          <div className="bg-white rounded-sm border border-cream-500 p-8 shadow-sm">
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin w-6 h-6 border-2 border-palm-500 border-t-transparent rounded-full" />
              <span className="ml-3 text-warm-gray-600">
                Checking generation status...
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Back link */}
      <Link
        href={backHref}
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
        {backLabel}
      </Link>

      {/* Wizard card */}
      <div className="max-w-xl mx-auto">
        <div className="bg-white rounded-sm border border-cream-500 p-8 shadow-sm">
          {/* Header with step indicator */}
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-semibold text-warm-gray-900">
              {wizardTitle}
            </h1>
            <span className="text-sm text-warm-gray-500">
              Step {currentStep} of 2
            </span>
          </div>

          {/* Error message */}
          {error && (
            <div className="rounded-sm bg-coral-50 border border-coral-200 p-4 text-coral-700 mb-6">
              {error}
            </div>
          )}

          {/* Step 1: Project Details */}
          {currentStep === 1 && (
            <>
              <ProjectForm
                formId={formId}
                onSubmit={handleSubmit}
                initialData={formData ?? undefined}
                isSubmitting={isSubmitting}
                showFileUpload={true}
                onFilesSelected={handleFilesSelected}
                onFileRemove={handleFileRemove}
                uploadedFiles={uploadedFiles}
                hideSubmitButton={true}
              />

              {/* Action buttons */}
              <div className="mt-8 flex justify-end gap-3 pt-4 border-t border-cream-200">
                <Link href={backHref}>
                  <Button variant="ghost">Cancel</Button>
                </Link>
                <Button
                  type="submit"
                  form={formId}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'Creating...' : 'Continue'}
                </Button>
              </div>
            </>
          )}

          {/* Step 2: Generation Progress */}
          {currentStep === 2 && projectId && (
            <GenerationProgress
              projectId={projectId}
              projectName={formData?.name ?? projectData?.name}
              onBack={handleBack}
              onGoToProject={handleGoToProject}
              onRetry={handleRetry}
            />
          )}
        </div>
      </div>
    </div>
  );
}
