'use client';

import { useState } from 'react';

interface CheckGroupProps {
  title: string;
  issueCount: number;
  badge?: string;
  defaultOpen: boolean;
  children: React.ReactNode;
}

export function CheckGroup({ title, issueCount, badge, defaultOpen, children }: CheckGroupProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border-t border-sand-200">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-sand-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg
            className={`w-3.5 h-3.5 text-warm-400 transition-transform ${isOpen ? 'rotate-90' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
          </svg>

          <span className="text-xs font-semibold text-warm-700">{title}</span>

          {issueCount > 0 ? (
            <span className="text-xs font-mono text-coral-600 bg-coral-50 px-1.5 py-0.5 rounded-sm">
              {issueCount} issue{issueCount !== 1 ? 's' : ''}
            </span>
          ) : (
            <span className="text-xs font-mono text-palm-600 bg-palm-50 px-1.5 py-0.5 rounded-sm">
              pass
            </span>
          )}
        </div>

        {badge && (
          <span className="text-xs text-lagoon-600 bg-lagoon-50 px-1.5 py-0.5 rounded-sm font-medium truncate max-w-[140px]">
            {badge}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="px-4 pb-3 space-y-1">
          {children}
        </div>
      )}
    </div>
  );
}
