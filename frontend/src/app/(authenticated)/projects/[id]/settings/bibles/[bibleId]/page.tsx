'use client';

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  useBible,
  useBiblePreview,
  useCreateBible,
  useUpdateBible,
  useDeleteBible,
  useExportBible,
} from '@/hooks/useBibles';
import { TagInput } from '@/components/brand-sections/editors/TagInput';
import { Button, Toast } from '@/components/ui';
import type {
  BibleQARules,
  BiblePreferredTerm,
  BibleBannedClaim,
  BibleFeatureAttribution,
  BibleTermContext,
} from '@/lib/api';

// =============================================================================
// Types
// =============================================================================

interface BibleFormData {
  name: string;
  slug: string;
  content_md: string;
  trigger_keywords: string[];
  is_active: boolean;
  qa_rules: BibleQARules;
}

type TabKey = 'overview' | 'content' | 'qa-rules' | 'preview';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'content', label: 'Content' },
  { key: 'qa-rules', label: 'QA Rules' },
  { key: 'preview', label: 'Preview' },
];

function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

const EMPTY_QA_RULES: BibleQARules = {
  preferred_terms: [],
  banned_claims: [],
  feature_attribution: [],
  term_context_rules: [],
};

const INITIAL_FORM: BibleFormData = {
  name: '',
  slug: '',
  content_md: '',
  trigger_keywords: [],
  is_active: true,
  qa_rules: EMPTY_QA_RULES,
};

// =============================================================================
// Overview Tab
// =============================================================================

function OverviewTab({
  form,
  isNew,
  onChange,
}: {
  form: BibleFormData;
  isNew: boolean;
  onChange: (patch: Partial<BibleFormData>) => void;
}) {
  return (
    <div className="space-y-6">
      {/* Name */}
      <div>
        <label className="block mb-1.5 text-sm font-medium text-warm-gray-700">
          Name <span className="text-coral-500">*</span>
        </label>
        <input
          type="text"
          value={form.name}
          onChange={(e) => {
            const name = e.target.value;
            const patch: Partial<BibleFormData> = { name };
            if (isNew) {
              patch.slug = slugify(name);
            }
            onChange(patch);
          }}
          placeholder="e.g. Tattoo Cartridge Needles"
          className="w-full px-3 py-2 border border-cream-400 rounded-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-2 focus:ring-palm-200 focus:outline-none transition-colors"
        />
      </div>

      {/* Slug */}
      <div>
        <label className="block mb-1.5 text-sm font-medium text-warm-gray-700">
          Slug
        </label>
        {isNew ? (
          <input
            type="text"
            value={form.slug}
            onChange={(e) => onChange({ slug: e.target.value })}
            placeholder="auto-generated-from-name"
            className="w-full px-3 py-2 border border-cream-400 rounded-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-2 focus:ring-palm-200 focus:outline-none transition-colors"
          />
        ) : (
          <div className="px-3 py-2 bg-cream-50 border border-cream-300 rounded-sm text-warm-gray-600 text-sm">
            {form.slug}
          </div>
        )}
      </div>

      {/* Trigger Keywords */}
      <div>
        <TagInput
          label="Trigger Keywords"
          value={form.trigger_keywords}
          onChange={(tags) => onChange({ trigger_keywords: tags })}
          placeholder="Type a keyword and press Enter..."
        />
        <p className="mt-1 text-xs text-warm-gray-500">
          Keywords that activate this bible during content generation
        </p>
      </div>

      {/* Status */}
      <div>
        <label className="block mb-1.5 text-sm font-medium text-warm-gray-700">
          Status
        </label>
        <select
          value={form.is_active ? 'active' : 'draft'}
          onChange={(e) => onChange({ is_active: e.target.value === 'active' })}
          className="w-48 px-3 py-2 border border-cream-400 rounded-sm text-warm-gray-900 bg-white focus:border-palm-400 focus:ring-2 focus:ring-palm-200 focus:outline-none transition-colors"
        >
          <option value="active">Active</option>
          <option value="draft">Draft</option>
        </select>
      </div>
    </div>
  );
}

// =============================================================================
// Content Tab
// =============================================================================

function ContentTab({
  form,
  onChange,
}: {
  form: BibleFormData;
  onChange: (patch: Partial<BibleFormData>) => void;
}) {
  const charCount = form.content_md.length;

  return (
    <div>
      <label className="block mb-1.5 text-sm font-medium text-warm-gray-700">
        Knowledge Document (Markdown)
      </label>
      <textarea
        value={form.content_md}
        onChange={(e) => onChange({ content_md: e.target.value })}
        rows={20}
        placeholder={`# Product Knowledge\n\n## Key Features\n- Feature 1: Description\n- Feature 2: Description\n\n## Terminology\n- **Correct term**: Use this instead of incorrect term\n\n## Common Mistakes\n- Never claim X because Y`}
        className="w-full px-3 py-2 border border-cream-400 rounded-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-2 focus:ring-palm-200 focus:outline-none transition-colors font-mono text-sm resize-y"
      />
      <div className="flex justify-end mt-1">
        <span
          className={`text-xs ${
            charCount > 8000 ? 'text-coral-500 font-medium' : 'text-warm-gray-500'
          }`}
        >
          {charCount.toLocaleString()} characters
          {charCount > 8000 && ' — consider splitting into multiple bibles'}
        </span>
      </div>
    </div>
  );
}

// =============================================================================
// QA Rules Tab
// =============================================================================

function RuleSection({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div className="border border-cream-300 rounded-sm">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-cream-50 transition-colors"
      >
        <span className="text-sm font-medium text-warm-gray-900">
          {title}
          <span className="ml-2 text-xs text-warm-gray-500">({count})</span>
        </span>
        <svg
          className={`w-4 h-4 text-warm-gray-500 transition-transform ${
            isOpen ? 'rotate-180' : ''
          }`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {isOpen && <div className="px-4 pb-4 border-t border-cream-200">{children}</div>}
    </div>
  );
}

function PreferredTermsTable({
  rules,
  onChange,
}: {
  rules: BiblePreferredTerm[];
  onChange: (rules: BiblePreferredTerm[]) => void;
}) {
  const addRow = () => {
    onChange([...rules, { use: '', instead_of: '' }]);
  };

  const updateRow = (index: number, field: keyof BiblePreferredTerm, value: string) => {
    const updated = rules.map((r, i) =>
      i === index ? { ...r, [field]: value } : r
    );
    onChange(updated);
  };

  const removeRow = (index: number) => {
    onChange(rules.filter((_, i) => i !== index));
  };

  return (
    <div className="mt-3">
      {rules.length > 0 && (
        <div className="grid grid-cols-[1fr_1fr_auto] gap-2 mb-2">
          <span className="text-xs font-medium text-warm-gray-600 uppercase">Use</span>
          <span className="text-xs font-medium text-warm-gray-600 uppercase">Instead Of</span>
          <span className="w-8" />
          {rules.map((rule, i) => (
            <div key={i} className="contents">
              <input
                type="text"
                value={rule.use}
                onChange={(e) => updateRow(i, 'use', e.target.value)}
                placeholder="Preferred term"
                className="px-2 py-1.5 border border-cream-400 rounded-sm text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-1 focus:ring-palm-200 focus:outline-none"
              />
              <input
                type="text"
                value={rule.instead_of}
                onChange={(e) => updateRow(i, 'instead_of', e.target.value)}
                placeholder="Avoid this term"
                className="px-2 py-1.5 border border-cream-400 rounded-sm text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-1 focus:ring-palm-200 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => removeRow(i)}
                className="w-8 h-8 flex items-center justify-center text-warm-gray-400 hover:text-coral-500 transition-colors"
                aria-label="Remove rule"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
      <button
        type="button"
        onClick={addRow}
        className="text-sm text-palm-600 hover:text-palm-700 font-medium"
      >
        + Add Rule
      </button>
    </div>
  );
}

function BannedClaimsTable({
  rules,
  onChange,
}: {
  rules: BibleBannedClaim[];
  onChange: (rules: BibleBannedClaim[]) => void;
}) {
  const addRow = () => {
    onChange([...rules, { claim: '', context: '', reason: '' }]);
  };

  const updateRow = (index: number, field: keyof BibleBannedClaim, value: string) => {
    const updated = rules.map((r, i) =>
      i === index ? { ...r, [field]: value } : r
    );
    onChange(updated);
  };

  const removeRow = (index: number) => {
    onChange(rules.filter((_, i) => i !== index));
  };

  return (
    <div className="mt-3">
      {rules.length > 0 && (
        <div className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2 mb-2">
          <span className="text-xs font-medium text-warm-gray-600 uppercase">Claim</span>
          <span className="text-xs font-medium text-warm-gray-600 uppercase">Context</span>
          <span className="text-xs font-medium text-warm-gray-600 uppercase">Reason</span>
          <span className="w-8" />
          {rules.map((rule, i) => (
            <div key={i} className="contents">
              <input
                type="text"
                value={rule.claim}
                onChange={(e) => updateRow(i, 'claim', e.target.value)}
                placeholder="Banned claim"
                className="px-2 py-1.5 border border-cream-400 rounded-sm text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-1 focus:ring-palm-200 focus:outline-none"
              />
              <input
                type="text"
                value={rule.context}
                onChange={(e) => updateRow(i, 'context', e.target.value)}
                placeholder="Context keyword"
                className="px-2 py-1.5 border border-cream-400 rounded-sm text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-1 focus:ring-palm-200 focus:outline-none"
              />
              <input
                type="text"
                value={rule.reason}
                onChange={(e) => updateRow(i, 'reason', e.target.value)}
                placeholder="Why it's banned"
                className="px-2 py-1.5 border border-cream-400 rounded-sm text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-1 focus:ring-palm-200 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => removeRow(i)}
                className="w-8 h-8 flex items-center justify-center text-warm-gray-400 hover:text-coral-500 transition-colors"
                aria-label="Remove rule"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
      <button
        type="button"
        onClick={addRow}
        className="text-sm text-palm-600 hover:text-palm-700 font-medium"
      >
        + Add Rule
      </button>
    </div>
  );
}

function FeatureAttributionTable({
  rules,
  onChange,
}: {
  rules: BibleFeatureAttribution[];
  onChange: (rules: BibleFeatureAttribution[]) => void;
}) {
  const addRow = () => {
    onChange([
      ...rules,
      { feature: '', correct_component: '', wrong_components: [] },
    ]);
  };

  const updateRow = (
    index: number,
    field: keyof BibleFeatureAttribution,
    value: string | string[]
  ) => {
    const updated = rules.map((r, i) =>
      i === index ? { ...r, [field]: value } : r
    );
    onChange(updated);
  };

  const removeRow = (index: number) => {
    onChange(rules.filter((_, i) => i !== index));
  };

  return (
    <div className="mt-3">
      {rules.length > 0 && (
        <div className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2 mb-2">
          <span className="text-xs font-medium text-warm-gray-600 uppercase">Feature</span>
          <span className="text-xs font-medium text-warm-gray-600 uppercase">Correct Component</span>
          <span className="text-xs font-medium text-warm-gray-600 uppercase">Wrong Components</span>
          <span className="w-8" />
          {rules.map((rule, i) => (
            <div key={i} className="contents">
              <input
                type="text"
                value={rule.feature}
                onChange={(e) => updateRow(i, 'feature', e.target.value)}
                placeholder="Feature name"
                className="px-2 py-1.5 border border-cream-400 rounded-sm text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-1 focus:ring-palm-200 focus:outline-none"
              />
              <input
                type="text"
                value={rule.correct_component}
                onChange={(e) =>
                  updateRow(i, 'correct_component', e.target.value)
                }
                placeholder="Belongs to..."
                className="px-2 py-1.5 border border-cream-400 rounded-sm text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-1 focus:ring-palm-200 focus:outline-none"
              />
              <input
                type="text"
                value={rule.wrong_components.join(', ')}
                onChange={(e) =>
                  updateRow(
                    i,
                    'wrong_components',
                    e.target.value
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean)
                  )
                }
                placeholder="Comma-separated"
                className="px-2 py-1.5 border border-cream-400 rounded-sm text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-1 focus:ring-palm-200 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => removeRow(i)}
                className="w-8 h-8 flex items-center justify-center text-warm-gray-400 hover:text-coral-500 transition-colors"
                aria-label="Remove rule"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
      <button
        type="button"
        onClick={addRow}
        className="text-sm text-palm-600 hover:text-palm-700 font-medium"
      >
        + Add Rule
      </button>
    </div>
  );
}

function TermContextTable({
  rules,
  onChange,
}: {
  rules: BibleTermContext[];
  onChange: (rules: BibleTermContext[]) => void;
}) {
  const addRow = () => {
    onChange([
      ...rules,
      { term: '', correct_context: [], wrong_contexts: [], explanation: '' },
    ]);
  };

  const updateRow = (
    index: number,
    field: keyof BibleTermContext,
    value: string | string[]
  ) => {
    const updated = rules.map((r, i) =>
      i === index ? { ...r, [field]: value } : r
    );
    onChange(updated);
  };

  const removeRow = (index: number) => {
    onChange(rules.filter((_, i) => i !== index));
  };

  return (
    <div className="mt-3">
      {rules.length > 0 && (
        <div className="grid grid-cols-[1fr_1fr_1fr_1fr_auto] gap-2 mb-2">
          <span className="text-xs font-medium text-warm-gray-600 uppercase">Term</span>
          <span className="text-xs font-medium text-warm-gray-600 uppercase">Correct Context</span>
          <span className="text-xs font-medium text-warm-gray-600 uppercase">Wrong Contexts</span>
          <span className="text-xs font-medium text-warm-gray-600 uppercase">Explanation</span>
          <span className="w-8" />
          {rules.map((rule, i) => (
            <div key={i} className="contents">
              <input
                type="text"
                value={rule.term}
                onChange={(e) => updateRow(i, 'term', e.target.value)}
                placeholder="Term"
                className="px-2 py-1.5 border border-cream-400 rounded-sm text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-1 focus:ring-palm-200 focus:outline-none"
              />
              <input
                type="text"
                value={rule.correct_context.join(', ')}
                onChange={(e) =>
                  updateRow(
                    i,
                    'correct_context',
                    e.target.value
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean)
                  )
                }
                placeholder="Comma-separated"
                className="px-2 py-1.5 border border-cream-400 rounded-sm text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-1 focus:ring-palm-200 focus:outline-none"
              />
              <input
                type="text"
                value={rule.wrong_contexts.join(', ')}
                onChange={(e) =>
                  updateRow(
                    i,
                    'wrong_contexts',
                    e.target.value
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean)
                  )
                }
                placeholder="Comma-separated"
                className="px-2 py-1.5 border border-cream-400 rounded-sm text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-1 focus:ring-palm-200 focus:outline-none"
              />
              <input
                type="text"
                value={rule.explanation}
                onChange={(e) => updateRow(i, 'explanation', e.target.value)}
                placeholder="Why this matters"
                className="px-2 py-1.5 border border-cream-400 rounded-sm text-sm text-warm-gray-900 placeholder:text-warm-gray-400 focus:border-palm-400 focus:ring-1 focus:ring-palm-200 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => removeRow(i)}
                className="w-8 h-8 flex items-center justify-center text-warm-gray-400 hover:text-coral-500 transition-colors"
                aria-label="Remove rule"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
      <button
        type="button"
        onClick={addRow}
        className="text-sm text-palm-600 hover:text-palm-700 font-medium"
      >
        + Add Rule
      </button>
    </div>
  );
}

function QARulesTab({
  form,
  onChange,
}: {
  form: BibleFormData;
  onChange: (patch: Partial<BibleFormData>) => void;
}) {
  const qa = form.qa_rules;

  const updateQA = useCallback(
    (field: keyof BibleQARules, value: unknown) => {
      onChange({
        qa_rules: { ...qa, [field]: value },
      });
    },
    [qa, onChange]
  );

  return (
    <div className="space-y-4">
      <p className="text-sm text-warm-gray-600">
        Structured rules used for automated quality checks on generated content.
      </p>

      <RuleSection title="Preferred Terms" count={qa.preferred_terms.length}>
        <PreferredTermsTable
          rules={qa.preferred_terms}
          onChange={(r) => updateQA('preferred_terms', r)}
        />
      </RuleSection>

      <RuleSection title="Banned Claims" count={qa.banned_claims.length}>
        <BannedClaimsTable
          rules={qa.banned_claims}
          onChange={(r) => updateQA('banned_claims', r)}
        />
      </RuleSection>

      <RuleSection title="Feature Attribution" count={qa.feature_attribution.length}>
        <FeatureAttributionTable
          rules={qa.feature_attribution}
          onChange={(r) => updateQA('feature_attribution', r)}
        />
      </RuleSection>

      <RuleSection title="Term Context Rules" count={qa.term_context_rules.length}>
        <TermContextTable
          rules={qa.term_context_rules}
          onChange={(r) => updateQA('term_context_rules', r)}
        />
      </RuleSection>
    </div>
  );
}

// =============================================================================
// Preview Tab
// =============================================================================

function PreviewTab({
  projectId,
  bibleId,
}: {
  projectId: string;
  bibleId: string;
}) {
  const { data: preview, isLoading, error } = useBiblePreview(projectId, bibleId);

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-4 bg-cream-300 rounded-sm w-48" />
        <div className="h-40 bg-cream-200 rounded-sm" />
        <div className="h-4 bg-cream-300 rounded-sm w-32" />
        <div className="h-20 bg-cream-200 rounded-sm" />
      </div>
    );
  }

  if (error || !preview) {
    return (
      <p className="text-sm text-warm-gray-500">
        Unable to load preview. Save the bible first.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      {/* Prompt Preview */}
      <div>
        <h3 className="text-sm font-medium text-warm-gray-700 mb-2">
          Prompt Preview
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          This is how domain knowledge appears in the content generation prompt:
        </p>
        <pre className="bg-cream-50 border border-cream-400 rounded-sm p-4 text-sm text-warm-gray-800 font-mono whitespace-pre-wrap overflow-x-auto max-h-[400px] overflow-y-auto">
          {preview.prompt_section}
        </pre>
      </div>

      {/* Matching Pages */}
      <div>
        <h3 className="text-sm font-medium text-warm-gray-700 mb-2">
          Matching Pages
        </h3>
        {preview.matched_pages.length > 0 ? (
          <>
            <p className="text-xs text-warm-gray-500 mb-3">
              This bible would match{' '}
              <span className="font-medium text-warm-gray-700">
                {preview.matched_pages.length}
              </span>{' '}
              of {preview.total_pages_in_project} pages with keywords:
            </p>
            <div className="border border-cream-300 rounded-sm divide-y divide-cream-200">
              {preview.matched_pages.map((page) => (
                <div
                  key={page.page_id}
                  className="flex items-center gap-3 px-4 py-2.5"
                >
                  <svg
                    className="w-4 h-4 text-palm-500 shrink-0"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-warm-gray-900 truncate">
                      {page.keyword}
                    </p>
                    <p className="text-xs text-warm-gray-400 truncate">
                      {page.url}
                    </p>
                  </div>
                  <span className="text-xs text-warm-gray-400 shrink-0">
                    via &ldquo;{page.matched_trigger}&rdquo;
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : preview.total_pages_in_project > 0 ? (
          <div className="bg-cream-50 border border-cream-300 rounded-sm px-4 py-6 text-center">
            <p className="text-sm text-warm-gray-600">
              No pages match the current trigger keywords.
            </p>
            <p className="text-xs text-warm-gray-400 mt-1">
              {preview.total_pages_in_project} pages with keywords exist in this project.
              Check the trigger keywords on the Overview tab.
            </p>
          </div>
        ) : (
          <div className="bg-cream-50 border border-cream-300 rounded-sm px-4 py-6 text-center">
            <p className="text-sm text-warm-gray-600">
              No pages with keywords in this project yet.
            </p>
            <p className="text-xs text-warm-gray-400 mt-1">
              Import pages and run keyword research to see matching results here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Main Editor Page
// =============================================================================

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-4 bg-cream-300 rounded-sm w-32 mb-6" />
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="h-7 bg-cream-300 rounded-sm w-48 mb-2" />
          <div className="h-4 bg-cream-300 rounded-sm w-32" />
        </div>
        <div className="h-10 bg-cream-300 rounded-sm w-24" />
      </div>
      <div className="flex gap-6">
        <div className="w-48 space-y-2">
          <div className="h-10 bg-cream-300 rounded-sm" />
          <div className="h-10 bg-cream-300 rounded-sm" />
          <div className="h-10 bg-cream-300 rounded-sm" />
        </div>
        <div className="flex-1 bg-white rounded-sm border border-cream-500 p-6 min-h-[400px]">
          <div className="space-y-3">
            <div className="h-4 bg-cream-300 rounded-sm w-full" />
            <div className="h-4 bg-cream-300 rounded-sm w-3/4" />
            <div className="h-4 bg-cream-300 rounded-sm w-5/6" />
          </div>
        </div>
      </div>
    </div>
  );
}

function NotFoundState({ projectId }: { projectId: string }) {
  return (
    <div className="text-center py-12">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-coral-50 mb-4">
        <svg
          className="w-8 h-8 text-coral-500"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h2 className="text-xl font-semibold text-warm-gray-900 mb-2">
        Bible Not Found
      </h2>
      <p className="text-warm-gray-600 text-sm mb-4">
        This bible may have been deleted or doesn&apos;t exist.
      </p>
      <Link
        href={`/projects/${projectId}/settings/bibles`}
        className="text-palm-600 hover:text-palm-700 text-sm font-medium"
      >
        Back to Knowledge Bibles
      </Link>
    </div>
  );
}

function BackLink({ projectId }: { projectId: string }) {
  return (
    <Link
      href={`/projects/${projectId}/settings/bibles`}
      className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
    >
      <svg
        className="w-4 h-4 mr-1"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M19 12H5M12 19l-7-7 7-7" />
      </svg>
      Knowledge Bibles
    </Link>
  );
}

export default function BibleEditorPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const bibleId = params.bibleId as string;
  const isNew = bibleId === 'new';

  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [form, setForm] = useState<BibleFormData>(INITIAL_FORM);
  const [initialForm, setInitialForm] = useState<BibleFormData>(INITIAL_FORM);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const deleteTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const formInitializedRef = useRef(false);
  const isSavingRef = useRef(false);

  const { data: bible, isLoading, error } = useBible(projectId, bibleId, {
    enabled: !isNew,
  });
  const createBible = useCreateBible();
  const updateBible = useUpdateBible();
  const deleteBible = useDeleteBible();
  const exportBibleMut = useExportBible();

  // Populate form from loaded bible — only on initial load, not on refetch
  useEffect(() => {
    if (bible && !formInitializedRef.current) {
      formInitializedRef.current = true;
      const loaded: BibleFormData = {
        name: bible.name,
        slug: bible.slug,
        content_md: bible.content_md,
        trigger_keywords: bible.trigger_keywords,
        is_active: bible.is_active,
        qa_rules: {
          preferred_terms: bible.qa_rules?.preferred_terms ?? [],
          banned_claims: bible.qa_rules?.banned_claims ?? [],
          feature_attribution: bible.qa_rules?.feature_attribution ?? [],
          term_context_rules: bible.qa_rules?.term_context_rules ?? [],
        },
      };
      setForm(loaded);
      setInitialForm(loaded);
    }
  }, [bible]);

  const isDirty = useMemo(
    () => JSON.stringify(form) !== JSON.stringify(initialForm),
    [form, initialForm]
  );

  // Warn on browser refresh/close with unsaved changes
  useEffect(() => {
    if (!isDirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [isDirty]);

  const handleChange = useCallback((patch: Partial<BibleFormData>) => {
    setForm((prev) => ({ ...prev, ...patch }));
  }, []);

  const handleSave = useCallback(async () => {
    if (isSavingRef.current) return;

    if (!form.name.trim()) {
      setToastMessage('Name is required');
      setToastVariant('error');
      setShowToast(true);
      return;
    }

    isSavingRef.current = true;

    try {
      if (isNew) {
        const result = await createBible.mutateAsync({
          projectId,
          data: {
            name: form.name,
            slug: form.slug || undefined,
            content_md: form.content_md,
            trigger_keywords: form.trigger_keywords,
            qa_rules: form.qa_rules,
            is_active: form.is_active,
          },
        });
        // Show toast before navigating so the user sees feedback
        setToastMessage('Bible created');
        setToastVariant('success');
        setShowToast(true);
        // Small delay to let the toast render before navigating
        setTimeout(() => {
          router.replace(
            `/projects/${projectId}/settings/bibles/${result.id}`
          );
        }, 600);
      } else {
        const result = await updateBible.mutateAsync({
          projectId,
          bibleId,
          data: {
            name: form.name,
            content_md: form.content_md,
            trigger_keywords: form.trigger_keywords,
            qa_rules: form.qa_rules,
            is_active: form.is_active,
          },
        });
        // Use server response as new baseline to avoid key-order mismatches
        const newBaseline: BibleFormData = {
          name: result.name,
          slug: result.slug,
          content_md: result.content_md,
          trigger_keywords: result.trigger_keywords,
          is_active: result.is_active,
          qa_rules: {
            preferred_terms: result.qa_rules?.preferred_terms ?? [],
            banned_claims: result.qa_rules?.banned_claims ?? [],
            feature_attribution: result.qa_rules?.feature_attribution ?? [],
            term_context_rules: result.qa_rules?.term_context_rules ?? [],
          },
        };
        setForm(newBaseline);
        setInitialForm(newBaseline);
        setToastMessage('Changes saved');
        setToastVariant('success');
        setShowToast(true);
      }
    } catch {
      setToastMessage('Failed to save');
      setToastVariant('error');
      setShowToast(true);
    } finally {
      isSavingRef.current = false;
    }
  }, [isNew, form, projectId, bibleId, createBible, updateBible, router]);

  const handleExport = useCallback(async () => {
    try {
      const result = await exportBibleMut.mutateAsync({
        projectId,
        bibleId,
      });
      const blob = new Blob([result.markdown], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = result.filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      // Revoke after a tick to let the browser initiate the download
      setTimeout(() => URL.revokeObjectURL(url), 100);
    } catch {
      setToastMessage('Failed to export');
      setToastVariant('error');
      setShowToast(true);
    }
  }, [exportBibleMut, projectId, bibleId]);

  const handleDelete = useCallback(async () => {
    if (!isConfirmingDelete) {
      setIsConfirmingDelete(true);
      deleteTimeoutRef.current = setTimeout(
        () => setIsConfirmingDelete(false),
        3000
      );
      return;
    }

    if (deleteTimeoutRef.current) clearTimeout(deleteTimeoutRef.current);

    try {
      await deleteBible.mutateAsync({ projectId, bibleId });
      router.push(`/projects/${projectId}/settings/bibles`);
    } catch {
      setIsConfirmingDelete(false);
      setToastMessage('Failed to delete');
      setToastVariant('error');
      setShowToast(true);
    }
  }, [isConfirmingDelete, deleteBible, projectId, bibleId, router]);

  // Cleanup delete timeout
  useEffect(() => {
    return () => {
      if (deleteTimeoutRef.current) clearTimeout(deleteTimeoutRef.current);
    };
  }, []);

  const isSaving = createBible.isPending || updateBible.isPending;

  // Loading state
  if (!isNew && isLoading) {
    return (
      <div>
        <BackLink projectId={projectId} />
        <LoadingSkeleton />
      </div>
    );
  }

  // Error / not-found state
  if (!isNew && (error || !bible)) {
    return (
      <div>
        <BackLink projectId={projectId} />
        <NotFoundState projectId={projectId} />
      </div>
    );
  }

  return (
    <div>
      <BackLink projectId={projectId} />

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-warm-gray-900 mb-1">
            {isNew ? 'New Bible' : form.name || 'Untitled Bible'}
          </h1>
          {!isNew && form.slug && (
            <p className="text-sm text-warm-gray-500">{form.slug}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!isNew && (
            <Button
              variant="secondary"
              onClick={handleExport}
              disabled={exportBibleMut.isPending}
            >
              {exportBibleMut.isPending ? 'Exporting...' : 'Export'}
            </Button>
          )}
          <Button
            onClick={handleSave}
            disabled={isSaving || (!isNew && !isDirty)}
          >
            {isSaving
              ? 'Saving...'
              : isNew
              ? 'Create Bible'
              : isDirty
              ? 'Save Changes'
              : 'Saved'}
          </Button>
        </div>
      </div>

      {/* Two-column layout: nav + content */}
      <div className="flex gap-6">
        {/* Tab nav */}
        <nav className="w-48 shrink-0">
          <div className="space-y-1">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`w-full text-left px-3 py-2 rounded-sm text-sm transition-colors ${
                  activeTab === tab.key
                    ? 'bg-palm-50 text-palm-700 font-medium'
                    : 'text-warm-gray-600 hover:bg-cream-50 hover:text-warm-gray-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Delete button at bottom of nav */}
          {!isNew && (
            <div className="mt-8 pt-4 border-t border-cream-300">
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleteBible.isPending}
                className="w-full text-left px-3 py-2 rounded-sm text-sm text-coral-600 hover:bg-coral-50 transition-colors disabled:opacity-50"
              >
                {deleteBible.isPending
                  ? 'Deleting...'
                  : isConfirmingDelete
                  ? 'Click again to confirm'
                  : 'Delete Bible'}
              </button>
            </div>
          )}
        </nav>

        {/* Content area */}
        <div className="flex-1 bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
          {activeTab === 'overview' && (
            <OverviewTab form={form} isNew={isNew} onChange={handleChange} />
          )}
          {activeTab === 'content' && (
            <ContentTab form={form} onChange={handleChange} />
          )}
          {activeTab === 'qa-rules' && (
            <QARulesTab form={form} onChange={handleChange} />
          )}
          {activeTab === 'preview' && !isNew && (
            <PreviewTab projectId={projectId} bibleId={bibleId} />
          )}
          {activeTab === 'preview' && isNew && (
            <p className="text-sm text-warm-gray-500">
              Save the bible first to see the preview.
            </p>
          )}
        </div>
      </div>

      {showToast && (
        <Toast
          message={toastMessage}
          variant={toastVariant}
          onClose={() => setShowToast(false)}
        />
      )}
    </div>
  );
}
