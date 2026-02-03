'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ProjectForm, type ProjectFormData } from '@/components/ProjectForm';
import { useCreateProject } from '@/hooks/use-projects';
import { Button } from '@/components/ui';

export default function CreateProjectPage() {
  const router = useRouter();
  const createProject = useCreateProject();
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(data: ProjectFormData) {
    setError(null);
    try {
      const project = await createProject.mutateAsync(data);
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to create project. Please try again.'
      );
    }
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
        Back to Dashboard
      </Link>

      {/* Form card */}
      <div className="max-w-xl mx-auto">
        <div className="bg-white rounded-sm border border-cream-500 p-8 shadow-sm">
          {/* Page title */}
          <h1 className="text-2xl font-semibold text-warm-gray-900 mb-6">
            Create New Project
          </h1>

          {/* Error message */}
          {error && (
            <div className="rounded-sm bg-coral-50 border border-coral-200 p-4 text-coral-700 mb-6">
              {error}
            </div>
          )}

          {/* Project form */}
          <ProjectForm
            onSubmit={handleSubmit}
            isSubmitting={createProject.isPending}
          />

          {/* Cancel button */}
          <div className="mt-4 flex justify-end">
            <Link href="/">
              <Button variant="ghost">Cancel</Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
