'use client';

import type { RedditProjectCard as RedditProjectCardData } from '@/lib/api';

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export function RedditProjectCard({ project }: { project: RedditProjectCardData }) {
  return (
    <div className="bg-white rounded-sm border border-sand-500 p-5 shadow-sm hover:shadow-md transition-shadow cursor-pointer">
      {/* Header: name + active badge */}
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-medium text-warm-gray-900 truncate pr-2">
          {project.name}
        </h3>
        <span
          className={`flex-shrink-0 inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm border ${
            project.is_active
              ? 'bg-palm-50 text-palm-700 border-palm-200'
              : 'bg-cream-100 text-warm-gray-500 border-cream-300'
          }`}
        >
          {project.is_active ? 'Active' : 'Inactive'}
        </span>
      </div>

      {/* Site URL */}
      <p className="text-xs text-warm-gray-500 mb-3 truncate">{project.site_url}</p>

      {/* Stats row */}
      <div className="flex items-center gap-4 text-sm text-warm-gray-600 mb-3">
        <span>
          <span className="font-medium text-warm-gray-900">{project.post_count}</span>{' '}
          {project.post_count === 1 ? 'post' : 'posts'}
        </span>
        <span>
          <span className="font-medium text-warm-gray-900">{project.comment_count}</span>{' '}
          {project.comment_count === 1 ? 'comment' : 'comments'}
        </span>
        {project.draft_count > 0 && (
          <span className="text-coral-600 font-medium">
            {project.draft_count} draft{project.draft_count !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Last activity */}
      <p className="text-xs text-warm-gray-400">
        Updated {formatRelativeTime(project.updated_at)}
      </p>
    </div>
  );
}
