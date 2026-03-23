'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useProjects } from '@/hooks/use-projects';
import { useAppConfig } from '@/hooks/use-app-config';
import { ProjectCard } from '@/components/ProjectCard';
import { Button, EmptyState } from '@/components/ui';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

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
  const { data, isLoading, error, refetch } = useProjects();
  const { data: appConfig } = useAppConfig();
  const [exporting, setExporting] = useState(false);

  const projects = data?.items ?? [];
  const hasProjects = projects.length > 0;
  const isLoremMode = appConfig?.content_mode === 'lorem';

  const handleExportXlsx = async () => {
    setExporting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/export/sites-xlsx`);
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || 'Export failed');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'sites-export.xlsx';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  // Sort by most recently updated first
  const sortedProjects = [...projects].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  );

  return (
    <div>
      {/* Header area with title and action */}
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-semibold text-warm-gray-900">Your Projects</h1>
        <div className="flex items-center gap-3">
          {isLoremMode && hasProjects && (
            <Button
              variant="secondary"
              onClick={handleExportXlsx}
              disabled={exporting}
            >
              {exporting ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Exporting...
                </>
              ) : (
                'Export All Sites (XLSX)'
              )}
            </Button>
          )}
          <Link href="/projects/new">
            <Button>+ New Project</Button>
          </Link>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-sm bg-coral-50 border border-coral-200 p-4 text-coral-700">
          <p>Failed to load projects. Please try again.</p>
          <p className="text-sm mt-1 text-coral-500">{error.message}</p>
          <button
            onClick={() => refetch()}
            className="mt-3 bg-palm-500 text-white rounded-sm px-4 py-2 text-sm hover:bg-palm-600"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading state */}
      {isLoading && <ProjectsGridSkeleton />}

      {/* Empty state */}
      {!isLoading && !error && !hasProjects && (
        <EmptyState
          icon={<FolderIcon />}
          title="No projects yet"
          description="Create your first project to get started."
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
