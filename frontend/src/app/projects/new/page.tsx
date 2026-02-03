'use client';

import { useCallback, useId, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ProjectForm, type ProjectFormData } from '@/components/ProjectForm';
import { type UploadedFile } from '@/components/FileUpload';
import { useCreateProject } from '@/hooks/use-projects';
import { uploadFileToProject } from '@/hooks/useProjectFiles';
import { useBrandConfigGeneration } from '@/hooks/useBrandConfigGeneration';
import { Button } from '@/components/ui';

type WizardStep = 1 | 2;

// Generation steps for the checklist display
const GENERATION_STEPS = [
  'brand_foundation',
  'target_audience',
  'voice_dimensions',
  'voice_characteristics',
  'writing_style',
  'vocabulary',
  'trust_elements',
  'examples_bank',
  'competitor_context',
  'ai_prompt_snippet',
] as const;

const STEP_DISPLAY_NAMES: Record<string, string> = {
  brand_foundation: 'Extracting brand foundation',
  target_audience: 'Building target audience personas',
  voice_dimensions: 'Analyzing voice dimensions (4 scales)',
  voice_characteristics: 'Defining voice characteristics',
  writing_style: 'Setting writing style rules',
  vocabulary: 'Building vocabulary guide',
  trust_elements: 'Compiling trust elements',
  examples_bank: 'Creating examples bank',
  competitor_context: 'Analyzing competitor context',
  ai_prompt_snippet: 'Generating AI prompt snippet',
};

export default function CreateProjectPage() {
  const router = useRouter();
  const createProject = useCreateProject();
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<WizardStep>(1);
  const [projectId, setProjectId] = useState<string | null>(null);

  // File upload state
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const fileIdCounter = useRef(0);

  // Form ID for external submission
  const formId = useId();
  const [formData, setFormData] = useState<ProjectFormData | null>(null);

  // Brand config generation - only enabled when we have a project
  const generation = useBrandConfigGeneration(projectId ?? '');

  // Track if files are being uploaded
  const [isUploadingFiles, setIsUploadingFiles] = useState(false);

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
      const project = await createProject.mutateAsync(data);
      setProjectId(project.id);

      // Upload any pending files
      if (pendingFiles.length > 0) {
        await uploadPendingFiles(project.id);
      }

      // Move to step 2 and start generation
      setCurrentStep(2);

      // Start brand config generation
      await generation.startGenerationAsync();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to create project. Please try again.'
      );
    }
  }

  // Handle back button (Step 2 -> Step 1)
  function handleBack() {
    setCurrentStep(1);
    // Reset generation state if going back
    setProjectId(null);
  }

  // Handle completion - go to project page
  function handleGoToProject() {
    if (projectId) {
      router.push(`/projects/${projectId}`);
    }
  }

  const isSubmitting =
    createProject.isPending ||
    isUploadingFiles ||
    generation.isStarting;

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
        Back to Dashboard
      </Link>

      {/* Wizard card */}
      <div className="max-w-xl mx-auto">
        <div className="bg-white rounded-sm border border-cream-500 p-8 shadow-sm">
          {/* Header with step indicator */}
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-semibold text-warm-gray-900">
              Create New Project
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
                <Link href="/">
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
          {currentStep === 2 && (
            <div className="space-y-6">
              {/* Generation header */}
              {generation.isComplete ? (
                <div className="text-center py-4">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-palm-100 flex items-center justify-center">
                    <svg
                      className="w-8 h-8 text-palm-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  </div>
                  <h2 className="text-xl font-semibold text-warm-gray-900 mb-2">
                    Project Created!
                  </h2>
                  <p className="text-warm-gray-600">
                    &ldquo;{formData?.name}&rdquo; is ready. Brand configuration has been
                    generated successfully.
                  </p>
                </div>
              ) : generation.isFailed ? (
                <div className="text-center py-4">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-coral-100 flex items-center justify-center">
                    <svg
                      className="w-8 h-8 text-coral-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                      />
                    </svg>
                  </div>
                  <h2 className="text-xl font-semibold text-warm-gray-900 mb-2">
                    Generation Failed
                  </h2>
                  <p className="text-coral-600">{generation.error}</p>
                </div>
              ) : (
                <div className="text-center py-4">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-palm-100 flex items-center justify-center animate-pulse">
                    <svg
                      className="w-8 h-8 text-palm-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M13 10V3L4 14h7v7l9-11h-7z"
                      />
                    </svg>
                  </div>
                  <h2 className="text-xl font-semibold text-warm-gray-900 mb-2">
                    Generating Brand Configuration...
                  </h2>
                </div>
              )}

              {/* Progress bar */}
              {!generation.isComplete && !generation.isFailed && (
                <div className="space-y-2">
                  <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-palm-500 transition-all duration-500 ease-out"
                      style={{ width: `${generation.progress}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-sm text-warm-gray-500">
                    <span>{generation.currentStepLabel || 'Starting...'}</span>
                    <span>{generation.progress}%</span>
                  </div>
                </div>
              )}

              {/* Generation steps checklist */}
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {GENERATION_STEPS.map((step, index) => {
                  const isComplete = index < generation.stepsCompleted;
                  const isCurrent =
                    index === generation.stepsCompleted &&
                    generation.isGenerating;

                  return (
                    <div
                      key={step}
                      className={`flex items-center gap-3 p-2 rounded-sm ${
                        isCurrent ? 'bg-palm-50' : ''
                      }`}
                    >
                      {/* Status icon */}
                      <div className="flex-shrink-0 w-5 h-5">
                        {isComplete ? (
                          <svg
                            className="w-5 h-5 text-palm-500"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M5 13l4 4L19 7"
                            />
                          </svg>
                        ) : isCurrent ? (
                          <svg
                            className="w-5 h-5 text-palm-500 animate-spin"
                            fill="none"
                            viewBox="0 0 24 24"
                          >
                            <circle
                              className="opacity-25"
                              cx="12"
                              cy="12"
                              r="10"
                              stroke="currentColor"
                              strokeWidth="4"
                            />
                            <path
                              className="opacity-75"
                              fill="currentColor"
                              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                            />
                          </svg>
                        ) : (
                          <div className="w-5 h-5 rounded-full border-2 border-warm-gray-300" />
                        )}
                      </div>

                      {/* Step name */}
                      <span
                        className={`text-sm ${
                          isComplete
                            ? 'text-warm-gray-600'
                            : isCurrent
                            ? 'text-palm-700 font-medium'
                            : 'text-warm-gray-400'
                        }`}
                      >
                        {STEP_DISPLAY_NAMES[step]}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Action buttons */}
              <div className="flex justify-end gap-3 pt-4 border-t border-cream-200">
                {generation.isComplete ? (
                  <Button onClick={handleGoToProject}>
                    Go to Project
                    <svg
                      className="w-4 h-4 ml-1"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 5l7 7-7 7"
                      />
                    </svg>
                  </Button>
                ) : generation.isFailed ? (
                  <>
                    <Button variant="ghost" onClick={handleBack}>
                      Back
                    </Button>
                    <Button onClick={handleGoToProject}>
                      Go to Project Anyway
                    </Button>
                  </>
                ) : (
                  <Button variant="ghost" disabled>
                    Please wait...
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
