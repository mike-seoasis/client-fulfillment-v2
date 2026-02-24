'use client';

import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

function EmptyState({ icon, title, description, action, className = '' }: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-12 px-6 text-center ${className}`}
    >
      {icon && (
        <div className="mb-4 text-warm-gray-400">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-medium text-warm-gray-800">
        {title}
      </h3>
      {description && (
        <p className="mt-2 text-sm text-warm-gray-500 max-w-sm">
          {description}
        </p>
      )}
      {action && (
        <div className="mt-6">
          {action}
        </div>
      )}
    </div>
  );
}

export { EmptyState, type EmptyStateProps };
