'use client';

import { useState } from 'react';
import { EmptySection } from './SectionCard';
import { type AIPromptSnippetData, type BaseSectionProps } from './types';

interface AIPromptSectionProps extends BaseSectionProps {
  data?: AIPromptSnippetData;
}

function CopyIcon({ className }: { className?: string }) {
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
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

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
      <polyline points="20,6 9,17 4,12" />
    </svg>
  );
}

/**
 * Displays the AI Prompt Snippet section with copy functionality.
 * Shows the condensed brand context snippet for use with AI writing tools.
 */
export function AIPromptSection({ data }: AIPromptSectionProps) {
  const [copied, setCopied] = useState(false);

  if (!data || !data.snippet) {
    return <EmptySection message="AI prompt snippet not available" />;
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(data.snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div>
      {/* Instructions */}
      <div className="mb-4">
        <p className="text-sm text-warm-gray-600">
          Use this snippet before any AI writing request to ensure on-brand output:
        </p>
      </div>

      {/* Snippet Container */}
      <div className="relative">
        {/* Copy Button */}
        <button
          onClick={handleCopy}
          className={`
            absolute top-3 right-3 z-10
            inline-flex items-center gap-1.5 px-3 py-1.5
            text-sm font-medium rounded-sm
            transition-all duration-150
            ${
              copied
                ? 'bg-palm-100 text-palm-700 border border-palm-300'
                : 'bg-white text-warm-gray-600 border border-cream-300 hover:bg-cream-50 hover:border-cream-400'
            }
          `}
        >
          {copied ? (
            <>
              <CheckIcon className="w-4 h-4" />
              Copied!
            </>
          ) : (
            <>
              <CopyIcon className="w-4 h-4" />
              Copy to Clipboard
            </>
          )}
        </button>

        {/* Snippet Content */}
        <div className="bg-warm-gray-900 rounded-sm p-5 pt-14">
          <pre className="text-sm text-warm-gray-100 whitespace-pre-wrap font-mono leading-relaxed">
            {data.snippet}
          </pre>
        </div>
      </div>

      {/* Usage Tip */}
      <div className="mt-4 p-3 bg-lagoon-50 border border-lagoon-200 rounded-sm">
        <p className="text-sm text-lagoon-700">
          <span className="font-semibold">Tip:</span> Paste this snippet at the beginning of your
          prompts when using ChatGPT, Claude, or other AI writing tools to maintain consistent brand voice.
        </p>
      </div>
    </div>
  );
}
