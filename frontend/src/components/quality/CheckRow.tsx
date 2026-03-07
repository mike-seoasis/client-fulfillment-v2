'use client';

interface CheckRowProps {
  label: string;
  count: number;
  scoreValue?: number;
}

export function CheckRow({ label, count, scoreValue }: CheckRowProps) {
  if (scoreValue !== undefined) {
    const clamped = Math.max(0, Math.min(1, scoreValue));
    return (
      <div className="flex items-center justify-between text-xs py-0.5">
        <span className="text-warm-600">{label}</span>
        <div className="flex items-center gap-2">
          <div className="w-16 h-1.5 bg-sand-200 rounded-sm overflow-hidden">
            <div
              className={`h-full rounded-sm ${clamped >= 0.7 ? 'bg-palm-400' : clamped >= 0.5 ? 'bg-sand-500' : 'bg-coral-400'}`}
              style={{ width: `${clamped * 100}%` }}
            />
          </div>
          <span className="font-mono text-warm-500 w-8 text-right">{clamped.toFixed(2)}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between text-xs py-0.5">
      <span className="text-warm-600">{label}</span>
      {count > 0 ? (
        <span className="text-coral-600 font-medium">{count} found</span>
      ) : (
        <span className="text-palm-600 font-medium">Pass</span>
      )}
    </div>
  );
}
