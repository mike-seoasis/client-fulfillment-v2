'use client';

import type { ParsedUrl } from './UrlUploader';

interface UrlPreviewListProps {
  urls: ParsedUrl[];
  onRemove: (normalizedUrl: string) => void;
  className?: string;
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M13 4L6 11L3 8" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 4L4 12M4 4l8 8" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M2 4h12M5.333 4V2.667a1.333 1.333 0 011.334-1.334h2.666a1.333 1.333 0 011.334 1.334V4M12.667 4v9.333a1.333 1.333 0 01-1.334 1.334H4.667a1.333 1.333 0 01-1.334-1.334V4h9.334z" />
    </svg>
  );
}

/**
 * URL preview list component with remove functionality
 * Shows all parsed URLs with validation status and remove buttons
 */
function UrlPreviewList({ urls, onRemove, className = '' }: UrlPreviewListProps) {
  const validCount = urls.filter((u) => u.isValid).length;
  const invalidCount = urls.length - validCount;

  if (urls.length === 0) {
    return (
      <div className={`text-center py-8 text-warm-gray-400 text-sm ${className}`}>
        Enter URLs above to see them listed here
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Count summary */}
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm text-warm-gray-600">
          <span className="font-medium text-warm-gray-800">{validCount}</span>{' '}
          {validCount === 1 ? 'URL' : 'URLs'} to process
          {invalidCount > 0 && (
            <span className="text-coral-500 ml-2">
              ({invalidCount} invalid)
            </span>
          )}
        </div>
        <div className="text-xs text-warm-gray-400">
          {urls.length} total
        </div>
      </div>

      {/* URL list */}
      <div className="max-h-64 overflow-y-auto border border-cream-300 rounded-sm">
        {urls.map((item) => (
          <div
            key={item.normalizedUrl}
            className={`flex items-center gap-2 px-3 py-2 border-b border-cream-200 last:border-b-0 group ${
              item.isValid ? 'bg-white' : 'bg-coral-50'
            }`}
          >
            {/* Validation indicator */}
            <div className="flex-shrink-0">
              {item.isValid ? (
                <div className="w-4 h-4 rounded-full bg-palm-100 flex items-center justify-center">
                  <CheckIcon className="w-2.5 h-2.5 text-palm-600" />
                </div>
              ) : (
                <div className="w-4 h-4 rounded-full bg-coral-100 flex items-center justify-center">
                  <XIcon className="w-2.5 h-2.5 text-coral-600" />
                </div>
              )}
            </div>

            {/* URL text */}
            <div
              className={`flex-1 min-w-0 text-sm font-mono truncate ${
                item.isValid ? 'text-warm-gray-700' : 'text-coral-600'
              }`}
              title={item.url}
            >
              {item.url}
            </div>

            {/* Invalid label */}
            {!item.isValid && (
              <span className="flex-shrink-0 text-xs text-coral-500 bg-coral-100 px-1.5 py-0.5 rounded">
                invalid
              </span>
            )}

            {/* Remove button */}
            <button
              type="button"
              onClick={() => onRemove(item.normalizedUrl)}
              className="flex-shrink-0 p-1 rounded hover:bg-cream-200 text-warm-gray-400 hover:text-coral-500 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
              aria-label={`Remove ${item.url}`}
            >
              <TrashIcon className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export { UrlPreviewList, type UrlPreviewListProps };
