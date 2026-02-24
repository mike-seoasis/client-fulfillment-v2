'use client';

import Link from 'next/link';
import { useRedditProjects } from '@/hooks/useReddit';
import { RedditProjectCard } from '@/components/RedditProjectCard';
import { Button, EmptyState } from '@/components/ui';

function ProjectsGridSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="bg-cream-200/50 rounded-sm p-5 animate-pulse"
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

function ChatBubbleIcon({ className }: { className?: string }) {
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
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

export default function RedditDashboard() {
  const { data, isLoading, error } = useRedditProjects();

  const projects = data?.items ?? [];
  const hasProjects = projects.length > 0;

  return (
    <div>
      {/* Header area with title and action */}
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-semibold text-warm-gray-900">Reddit Projects</h1>
        <Link href="/projects/new?flow=reddit">
          <Button>+ New Project</Button>
        </Link>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-sm bg-coral-50 border border-coral-200 p-4 text-coral-700">
          Failed to load Reddit projects. Please try again.
        </div>
      )}

      {/* Loading state */}
      {isLoading && <ProjectsGridSkeleton />}

      {/* Empty state */}
      {!isLoading && !error && !hasProjects && (
        <EmptyState
          icon={<ChatBubbleIcon />}
          title="No Reddit projects yet"
          description="Create a new project or enable Reddit on an existing AI SEO project."
          action={
            <Link href="/projects/new?flow=reddit">
              <Button>Create Reddit Project</Button>
            </Link>
          }
        />
      )}

      {/* Projects grid */}
      {!isLoading && !error && hasProjects && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((project) => (
            <Link key={project.id} href={`/reddit/${project.id}`} className="block">
              <RedditProjectCard project={project} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
