'use client';

export interface CrawlProgressProps {
  /** Number of pages completed */
  completed: number;
  /** Total number of pages to process */
  total: number;
  /** Optional label for the progress bar (defaults to "Progress") */
  label?: string;
  /** Whether to show the percentage value */
  showPercentage?: boolean;
}

/**
 * CrawlProgress - A progress bar component for displaying crawl progress.
 * Shows completed/total count with an animated progress bar.
 */
export function CrawlProgress({
  completed,
  total,
  label = 'Progress',
  showPercentage = true,
}: CrawlProgressProps) {
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="mb-6">
      {/* Header with label and counts */}
      <div className="flex justify-between items-baseline text-sm mb-2">
        <span className="text-warm-gray-600">{label}</span>
        <div className="flex items-baseline gap-2">
          <span className="text-warm-gray-600">
            {completed} of {total}
          </span>
          {showPercentage && (
            <span className="text-warm-gray-500 text-xs font-medium">
              ({percentage}%)
            </span>
          )}
        </div>
      </div>

      {/* Progress bar track */}
      <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
        {/* Progress bar fill with animation */}
        <div
          className="h-full bg-palm-500 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${percentage}%` }}
          role="progressbar"
          aria-valuenow={completed}
          aria-valuemin={0}
          aria-valuemax={total}
          aria-label={`${label}: ${completed} of ${total} (${percentage}%)`}
        />
      </div>
    </div>
  );
}

export default CrawlProgress;
