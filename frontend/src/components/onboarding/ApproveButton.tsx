'use client';

interface ApproveButtonProps {
  /** Whether the keyword is currently approved */
  isApproved: boolean;
  /** Whether the approve operation is in progress */
  isLoading?: boolean;
  /** Whether the button is disabled (e.g., no keyword generated) */
  disabled?: boolean;
  /** Callback when approve button is clicked */
  onApprove: () => void | Promise<void>;
  /** Callback when unapprove is clicked (optional - if not provided, approved state is not clickable) */
  onUnapprove?: () => void | Promise<void>;
}

// SVG Icons
function CheckIcon({ className }: { className?: string }) {
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
      <polyline points="20 6 9 17 4 12" />
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
 * ApproveButton component - a button for approving/unapproving keywords.
 *
 * Features:
 * - Shows 'Approve' button when not approved
 * - Shows checkmark when approved (clickable to unapprove if onUnapprove provided)
 * - Clicking toggles approval state via API
 * - Shows loading state during toggle
 * - Uses palm-500 for approved state
 */
export function ApproveButton({
  isApproved,
  isLoading = false,
  disabled = false,
  onApprove,
  onUnapprove,
}: ApproveButtonProps) {
  if (isApproved) {
    // Approved state - show checkmark badge (clickable if onUnapprove provided)
    if (onUnapprove) {
      return (
        <button
          onClick={onUnapprove}
          disabled={isLoading}
          className="flex items-center gap-1 px-2 py-1 bg-palm-100 text-palm-700 hover:bg-palm-200 rounded-sm text-xs font-medium transition-colors disabled:opacity-50"
          title="Click to unapprove"
        >
          {isLoading ? (
            <>
              <SpinnerIcon className="w-4 h-4 animate-spin" />
              <span>Updating...</span>
            </>
          ) : (
            <>
              <CheckIcon className="w-4 h-4" />
              <span>Approved</span>
            </>
          )}
        </button>
      );
    }
    // No unapprove handler - show static badge
    return (
      <div
        className="flex items-center gap-1 px-2 py-1 bg-palm-100 text-palm-700 rounded-sm text-xs font-medium"
        title="Approved"
      >
        <CheckIcon className="w-4 h-4" />
        <span>Approved</span>
      </div>
    );
  }

  if (disabled) {
    // Disabled state (e.g., no keyword generated)
    return (
      <span className="text-xs text-warm-gray-400 px-2 py-1">
        Pending
      </span>
    );
  }

  // Not approved - show approve button
  return (
    <button
      onClick={onApprove}
      disabled={isLoading}
      className="flex items-center gap-1 px-2 py-1 bg-lagoon-100 text-lagoon-700 hover:bg-lagoon-200 rounded-sm text-xs font-medium transition-colors disabled:opacity-50"
    >
      {isLoading ? (
        <>
          <SpinnerIcon className="w-4 h-4 animate-spin" />
          <span>Approving...</span>
        </>
      ) : (
        <>
          <CheckIcon className="w-4 h-4" />
          <span>Approve</span>
        </>
      )}
    </button>
  );
}

export default ApproveButton;
