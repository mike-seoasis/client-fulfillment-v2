'use client';

import { useRouter } from 'next/navigation';
import { formatDistanceToNow } from 'date-fns';
import { Card } from '@/components/ui';
import type { Project } from '@/hooks/use-projects';

interface ProjectCardProps {
  project: Project;
}

function ProjectCard({ project }: ProjectCardProps) {
  const router = useRouter();

  const handleClick = () => {
    router.push(`/projects/${project.id}`);
  };

  const lastActivity = formatDistanceToNow(new Date(project.updated_at), {
    addSuffix: true,
  });

  return (
    <Card onClick={handleClick} className="p-5">
      <div className="space-y-3">
        {/* Project name */}
        <h3 className="text-lg font-semibold text-warm-gray-900 truncate">
          {project.name}
        </h3>

        {/* Site URL */}
        <p className="text-sm text-warm-gray-500 truncate">{project.site_url}</p>

        {/* Placeholder metrics */}
        <div className="flex items-center gap-4 text-sm text-warm-gray-600">
          <span>0 pages</span>
          <span className="text-warm-gray-300">•</span>
          <span>0 clusters</span>
          <span className="text-warm-gray-300">•</span>
          <span>0 pending</span>
        </div>

        {/* Last activity */}
        <p className="text-xs text-warm-gray-400">Last activity {lastActivity}</p>
      </div>
    </Card>
  );
}

export { ProjectCard, type ProjectCardProps };
