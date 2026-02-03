'use client';

import Link from 'next/link';
import { useProjects } from '@/hooks/use-projects';
import { ProjectCard } from '@/components/ProjectCard';
import { Button, EmptyState } from '@/components/ui';

function ProjectsGridSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="bg-cream-200/50 rounded-xl p-5 animate-pulse"
        >
          <div className="space-y-3">
            <div className="h-6 bg-cream-300 rounded w-3/4" />
            <div className="h-4 bg-cream-300 rounded w-full" />
            <div className="h-4 bg-cream-300 rounded w-1/2" />
            <div className="h-3 bg-cream-300 rounded w-1/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

function FolderIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="48"
      height="48"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  );
}

export default function Dashboard() {
  const { data, isLoading, error } = useProjects();

  const projects = data?.items ?? [];
  const hasProjects = projects.length > 0;

  // Sort by most recently updated first
  const sortedProjects = [...projects].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  );

  return (
    <div>
      {/* Header area with title and action */}
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-semibold text-warm-gray-900">Your Projects</h1>
        <Link href="/projects/new">
          <Button>+ New Project</Button>
        </Link>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-lg bg-coral-50 border border-coral-200 p-4 text-coral-700">
          Failed to load projects. Please try again.
        </div>
      )}

      {/* Loading state */}
      {isLoading && <ProjectsGridSkeleton />}

      {/* Empty state */}
      {!isLoading && !error && !hasProjects && (
        <EmptyState
          icon={<FolderIcon />}
          title="No projects yet"
          description="Create your first project to get started with client onboarding."
          action={
            <Link href="/projects/new">
              <Button>Create First Project</Button>
            </Link>
          }
        />
      )}

      {/* Projects grid */}
      {!isLoading && !error && hasProjects && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {sortedProjects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </div>
  );
}
