'use client';

import { useCallback, useId, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ProjectForm, type ProjectFormData } from '@/components/ProjectForm';
import { type UploadedFile } from '@/components/FileUpload';
import { GenerationProgress } from '@/components/GenerationProgress';
import { useCreateProject } from '@/hooks/use-projects';
import { uploadFileToProject } from '@/hooks/useProjectFiles';
import { useStartBrandConfigGeneration } from '@/hooks/useBrandConfigGeneration';
import { Button } from '@/components/ui';

type WizardStep = 1 | 2;

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

  // Brand config generation mutation - use startGenerationAsync directly
  const startGeneration = useStartBrandConfigGeneration(projectId ?? '');

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
      await startGeneration.mutateAsync();
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
    startGeneration.isPending;

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
          {currentStep === 2 && projectId && (
            <GenerationProgress
              projectId={projectId}
              projectName={formData?.name}
              onBack={handleBack}
              onGoToProject={handleGoToProject}
            />
          )}
        </div>
      </div>
    </div>
  );
}
