'use client';

import { type ReactNode } from 'react';

/**
 * Brand config section names as they appear in the v2_schema.
 * Order matches the wireframe and brand guidelines bible.
 */
export const BRAND_SECTIONS = [
  { key: 'brand_foundation', label: 'Brand Foundation' },
  { key: 'target_audience', label: 'Target Audience' },
  { key: 'voice_dimensions', label: 'Voice Dimensions' },
  { key: 'voice_characteristics', label: 'Voice Characteristics' },
  { key: 'writing_style', label: 'Writing Style' },
  { key: 'vocabulary', label: 'Vocabulary' },
  { key: 'trust_elements', label: 'Trust Elements' },
  { key: 'examples_bank', label: 'Examples Bank' },
  { key: 'competitor_context', label: 'Competitor Context' },
  { key: 'ai_prompt_snippet', label: 'AI Prompt' },
] as const;

export type SectionKey = (typeof BRAND_SECTIONS)[number]['key'];

interface SourceDocument {
  id: string;
  filename: string;
}

interface SectionNavProps {
  /** Currently active section key */
  activeSection: SectionKey;
  /** Callback when a section tab is clicked */
  onSectionChange: (section: SectionKey) => void;
  /** List of source documents to display */
  sourceDocuments?: SourceDocument[];
  /** Optional callback when upload button is clicked */
  onUploadClick?: () => void;
  /** Additional content to render below the nav */
  children?: ReactNode;
}

function DocumentIcon({ className }: { className?: string }) {
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
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14,2 14,8 20,8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  );
}

function PlusIcon({ className }: { className?: string }) {
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
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

/**
 * Vertical navigation tabs for brand configuration sections.
 * Displays section list with active indicator and source documents.
 */
export function SectionNav({
  activeSection,
  onSectionChange,
  sourceDocuments = [],
  onUploadClick,
}: SectionNavProps) {
  return (
    <nav className="w-56 flex-shrink-0">
      {/* Section Tabs */}
      <div className="mb-6">
        <h2 className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider mb-3 px-2">
          Sections
        </h2>
        <ul className="space-y-1">
          {BRAND_SECTIONS.map(({ key, label }) => {
            const isActive = activeSection === key;
            return (
              <li key={key}>
                <button
                  onClick={() => onSectionChange(key)}
                  className={`
                    w-full text-left px-3 py-2 rounded-sm text-sm transition-colors duration-150
                    flex items-center gap-2
                    ${
                      isActive
                        ? 'bg-palm-50 text-palm-700 font-medium'
                        : 'text-warm-gray-600 hover:bg-cream-100 hover:text-warm-gray-900'
                    }
                  `}
                >
                  {/* Active indicator dot */}
                  <span
                    className={`
                      w-1.5 h-1.5 rounded-full flex-shrink-0
                      ${isActive ? 'bg-palm-500' : 'bg-warm-gray-300'}
                    `}
                  />
                  {label}
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Divider */}
      <hr className="border-cream-400 my-4" />

      {/* Source Documents */}
      <div>
        <h2 className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider mb-3 px-2">
          Source Documents
        </h2>
        {sourceDocuments.length > 0 ? (
          <ul className="space-y-1">
            {sourceDocuments.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center gap-2 px-3 py-1.5 text-sm text-warm-gray-600"
              >
                <DocumentIcon className="w-4 h-4 text-warm-gray-400 flex-shrink-0" />
                <span className="truncate" title={doc.filename}>
                  {doc.filename}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-3 py-1.5 text-sm text-warm-gray-400 italic">
            No documents uploaded
          </p>
        )}

        {/* Upload button */}
        {onUploadClick && (
          <button
            onClick={onUploadClick}
            className="mt-2 w-full flex items-center gap-2 px-3 py-1.5 text-sm text-palm-600 hover:text-palm-700 hover:bg-palm-50 rounded-sm transition-colors duration-150"
          >
            <PlusIcon className="w-4 h-4" />
            Upload
          </button>
        )}
      </div>
    </nav>
  );
}

export type { SourceDocument };
