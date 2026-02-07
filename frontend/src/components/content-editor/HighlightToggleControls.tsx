'use client';

import { useState, useCallback } from 'react';

export interface HighlightVisibility {
  keyword: boolean;
  lsi: boolean;
  trope: boolean;
}

/** Returns CSS class names to add to the editor container for hidden layers. */
export function highlightVisibilityClasses(v: HighlightVisibility): string {
  const classes: string[] = [];
  if (!v.keyword) classes.push('hide-hl-keyword');
  if (!v.lsi) classes.push('hide-hl-lsi');
  if (!v.trope) classes.push('hide-hl-trope');
  return classes.join(' ');
}

interface HighlightToggleControlsProps {
  onChange: (visibility: HighlightVisibility) => void;
}

export function HighlightToggleControls({ onChange }: HighlightToggleControlsProps) {
  const [visibility, setVisibility] = useState<HighlightVisibility>({
    keyword: true,
    lsi: true,
    trope: true,
  });

  const toggle = useCallback(
    (layer: keyof HighlightVisibility) => {
      setVisibility((prev) => {
        const next = { ...prev, [layer]: !prev[layer] };
        onChange(next);
        return next;
      });
    },
    [onChange],
  );

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-warm-500 mr-1">Highlights</span>

      {/* Keywords + Vars toggle */}
      <button
        type="button"
        onClick={() => toggle('keyword')}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-medium border transition-all"
        style={{
          opacity: visibility.keyword ? 1 : 0.4,
          background: 'rgba(238, 200, 70, 0.15)',
          borderColor: 'rgba(238, 200, 70, 0.4)',
          color: '#8B7520',
        }}
      >
        <span
          className="w-2 h-2 rounded-full"
          style={{ background: '#EEC846' }}
        />
        Keywords + Vars
      </button>

      {/* LSI Terms toggle */}
      <button
        type="button"
        onClick={() => toggle('lsi')}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-medium border transition-all"
        style={{
          opacity: visibility.lsi ? 1 : 0.4,
          background: 'rgba(42, 157, 143, 0.1)',
          borderColor: 'rgba(42, 157, 143, 0.3)',
          color: '#1A635B',
        }}
      >
        <span className="w-2 h-2 rounded-full bg-lagoon-500" />
        LSI Terms
      </button>

      {/* Issues toggle */}
      <button
        type="button"
        onClick={() => toggle('trope')}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-medium border transition-all"
        style={{
          opacity: visibility.trope ? 1 : 0.4,
          background: 'rgba(224, 122, 95, 0.1)',
          borderColor: 'rgba(224, 122, 95, 0.3)',
          color: '#B24E36',
        }}
      >
        <span className="w-2 h-2 rounded-full bg-coral-500" />
        Issues
      </button>
    </div>
  );
}
