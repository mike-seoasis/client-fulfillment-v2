'use client';

interface ScoreBarProps {
  /** Value between 0.0 and 1.0 */
  value: number;
  /** Show numeric value to the right */
  showValue?: boolean;
}

function getBarColor(v: number): string {
  if (v >= 0.8) return 'bg-palm-500';
  if (v >= 0.7) return 'bg-palm-400';
  if (v >= 0.5) return 'bg-sand-500';
  if (v >= 0.3) return 'bg-coral-400';
  return 'bg-coral-500';
}

export function ScoreBar({ value, showValue = true }: ScoreBarProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const colorClass = getBarColor(clamped);

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-sand-200 rounded-sm overflow-hidden">
        <div
          className={`h-full rounded-sm ${colorClass}`}
          style={{ width: `${clamped * 100}%` }}
        />
      </div>
      {showValue && (
        <span className="text-xs font-mono text-warm-500 w-8 text-right">
          {clamped.toFixed(2)}
        </span>
      )}
    </div>
  );
}
