'use client';

import { useState, useRef, useEffect } from 'react';

interface PriorityToggleProps {
  /** Whether the page is currently marked as priority */
  isPriority: boolean;
  /** Whether the toggle is disabled (e.g., no keyword generated) */
  disabled?: boolean;
  /** Whether a toggle operation is in progress */
  isLoading?: boolean;
  /** Callback when toggle is clicked */
  onToggle: () => void | Promise<void>;
}

// SVG Icons
function StarIcon({ className, filled }: { className?: string; filled?: boolean }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill={filled ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" opacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" />
    </svg>
  );
}

/**
 * Simple tooltip component that appears on hover.
 */
function Tooltip({
  text,
  children,
}: {
  text: string;
  children: React.ReactNode;
}) {
  const [isVisible, setIsVisible] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isVisible && triggerRef.current && tooltipRef.current) {
      const triggerRect = triggerRef.current.getBoundingClientRect();
      const tooltipRect = tooltipRef.current.getBoundingClientRect();

      // Position tooltip above the trigger, centered
      setPosition({
        top: triggerRect.top - tooltipRect.height - 8,
        left: triggerRect.left + (triggerRect.width / 2) - (tooltipRect.width / 2),
      });
    }
  }, [isVisible]);

  return (
    <div
      ref={triggerRef}
      className="relative inline-block"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
    >
      {children}
      {isVisible && (
        <div
          ref={tooltipRef}
          className="fixed z-50 px-2 py-1 text-xs text-white bg-warm-gray-800 rounded-sm shadow-lg whitespace-nowrap"
          style={{ top: position.top, left: position.left }}
        >
          {text}
          {/* Tooltip arrow */}
          <div className="absolute left-1/2 -translate-x-1/2 -bottom-1 w-2 h-2 bg-warm-gray-800 rotate-45" />
        </div>
      )}
    </div>
  );
}

/**
 * PriorityToggle component - a star toggle for marking pages as priority for internal linking.
 *
 * Features:
 * - Shows star icon (filled when priority, empty when not)
 * - Clicking toggles priority via API
 * - Shows loading state during toggle
 * - Tooltip explains 'Mark as priority for internal linking'
 * - Uses palm-500 color for filled star
 */
export function PriorityToggle({
  isPriority,
  disabled = false,
  isLoading = false,
  onToggle,
}: PriorityToggleProps) {
  const tooltipText = isPriority
    ? 'Remove priority'
    : 'Mark as priority for internal linking';

  return (
    <Tooltip text={tooltipText}>
      <button
        onClick={onToggle}
        disabled={disabled || isLoading}
        className={`flex-shrink-0 p-1 rounded-sm transition-colors ${
          !disabled && !isLoading
            ? 'hover:bg-cream-200 cursor-pointer'
            : 'cursor-not-allowed opacity-50'
        }`}
        aria-label={tooltipText}
        aria-pressed={isPriority}
      >
        {isLoading ? (
          <SpinnerIcon className="w-5 h-5 text-warm-gray-400 animate-spin" />
        ) : (
          <StarIcon
            className={`w-5 h-5 ${
              isPriority ? 'text-palm-500' : 'text-warm-gray-300'
            }`}
            filled={isPriority}
          />
        )}
      </button>
    </Tooltip>
  );
}

export default PriorityToggle;
