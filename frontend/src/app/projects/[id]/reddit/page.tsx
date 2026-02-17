'use client';

import { useState, useCallback, useMemo, type KeyboardEvent } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import { useRedditConfig, useUpsertRedditConfig } from '@/hooks/useReddit';
import { Button, Toast } from '@/components/ui';

// =============================================================================
// ICONS
// =============================================================================

function BackArrowIcon({ className }: { className?: string }) {
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
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
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
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  );
}

// =============================================================================
// TAG INPUT COMPONENT
// =============================================================================

interface TagInputProps {
  label: string;
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  prefix?: string;
}

function TagInput({ label, tags, onChange, placeholder, prefix }: TagInputProps) {
  const [inputValue, setInputValue] = useState('');
  const inputId = label.toLowerCase().replace(/\s+/g, '-');

  const addTag = useCallback(
    (raw: string) => {
      const value = raw.trim();
      if (value && !tags.includes(value)) {
        onChange([...tags, value]);
      }
      setInputValue('');
    },
    [tags, onChange],
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter' || e.key === ',') {
        e.preventDefault();
        addTag(inputValue);
      }
      if (e.key === 'Backspace' && inputValue === '' && tags.length > 0) {
        onChange(tags.slice(0, -1));
      }
    },
    [inputValue, tags, onChange, addTag],
  );

  const removeTag = useCallback(
    (index: number) => {
      onChange(tags.filter((_, i) => i !== index));
    },
    [tags, onChange],
  );

  return (
    <div className="w-full">
      <label htmlFor={inputId} className="block mb-1.5 text-sm font-medium text-warm-gray-700">
        {label}
      </label>
      <div className="flex flex-wrap items-center gap-1.5 px-3 py-2 bg-white border border-cream-400 rounded-sm hover:border-cream-500 focus-within:border-palm-400 focus-within:ring-2 focus-within:ring-palm-200 focus-within:ring-offset-1 transition-colors duration-150 min-h-[42px]">
        {tags.map((tag, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-1 px-2 py-0.5 bg-palm-50 text-palm-700 text-sm rounded-sm border border-palm-200"
          >
            {prefix}{tag}
            <button
              type="button"
              onClick={() => removeTag(i)}
              className="hover:text-palm-900 transition-colors"
              aria-label={`Remove ${tag}`}
            >
              <XIcon className="w-3 h-3" />
            </button>
          </span>
        ))}
        <input
          id={inputId}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            if (inputValue.trim()) addTag(inputValue);
          }}
          placeholder={tags.length === 0 ? placeholder : ''}
          className="flex-1 min-w-[120px] text-sm text-warm-gray-900 placeholder:text-warm-gray-400 outline-none bg-transparent"
        />
      </div>
      <p className="mt-1 text-xs text-warm-gray-400">Press Enter or comma to add</p>
    </div>
  );
}

// =============================================================================
// TOGGLE SWITCH
// =============================================================================

function ToggleSwitch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`
        relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200
        focus:outline-none focus:ring-2 focus:ring-palm-400 focus:ring-offset-2
        ${checked ? 'bg-palm-500' : 'bg-cream-300'}
      `}
    >
      <span
        className={`
          inline-block h-4 w-4 rounded-full bg-white shadow transition-transform duration-200
          ${checked ? 'translate-x-6' : 'translate-x-1'}
        `}
      />
    </button>
  );
}

// =============================================================================
// LOADING & ERROR STATES
// =============================================================================

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-4 bg-cream-300 rounded w-32 mb-6" />
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="h-7 bg-cream-300 rounded w-64 mb-2" />
          <div className="h-4 bg-cream-300 rounded w-40" />
        </div>
        <div className="h-6 bg-cream-300 rounded w-11" />
      </div>
      <div className="bg-white rounded-sm border border-cream-500 p-6 space-y-6">
        <div className="h-10 bg-cream-300 rounded w-full" />
        <div className="h-10 bg-cream-300 rounded w-full" />
        <div className="h-10 bg-cream-300 rounded w-full" />
        <div className="h-24 bg-cream-300 rounded w-full" />
      </div>
    </div>
  );
}

// =============================================================================
// TIME RANGE OPTIONS
// =============================================================================

const TIME_RANGE_OPTIONS = [
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
];

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function ProjectRedditConfigPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const { data: existingConfig, isLoading: isConfigLoading } = useRedditConfig(projectId);
  const upsertMutation = useUpsertRedditConfig(projectId);

  // Form state
  const [isActive, setIsActive] = useState<boolean | null>(null);
  const [searchKeywords, setSearchKeywords] = useState<string[] | null>(null);
  const [targetSubreddits, setTargetSubreddits] = useState<string[] | null>(null);
  const [bannedSubreddits, setBannedSubreddits] = useState<string[] | null>(null);
  const [competitors, setCompetitors] = useState<string[] | null>(null);
  const [commentInstructions, setCommentInstructions] = useState<string | null>(null);
  const [nicheTags, setNicheTags] = useState<string[] | null>(null);
  const [timeRange, setTimeRange] = useState<string | null>(null);
  const [maxPosts, setMaxPosts] = useState<string | null>(null);

  // Toast
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');

  const isLoading = isProjectLoading || isConfigLoading;

  // Derive current values: user edits take priority, then existing config, then defaults
  const config = existingConfig ?? null;

  const currentIsActive = isActive ?? config?.is_active ?? true;
  const currentSearchKeywords = useMemo(
    () => searchKeywords ?? config?.search_keywords ?? [],
    [searchKeywords, config?.search_keywords],
  );
  const currentTargetSubreddits = useMemo(
    () => targetSubreddits ?? config?.target_subreddits ?? [],
    [targetSubreddits, config?.target_subreddits],
  );
  const currentBannedSubreddits = useMemo(
    () => bannedSubreddits ?? config?.banned_subreddits ?? [],
    [bannedSubreddits, config?.banned_subreddits],
  );
  const currentCompetitors = useMemo(
    () => competitors ?? config?.competitors ?? [],
    [competitors, config?.competitors],
  );
  const currentCommentInstructions = commentInstructions ?? config?.comment_instructions ?? '';
  const currentNicheTags = useMemo(
    () => nicheTags ?? config?.niche_tags ?? [],
    [nicheTags, config?.niche_tags],
  );
  const currentTimeRange =
    timeRange ??
    (config?.discovery_settings as Record<string, string> | null)?.time_range ??
    '7d';
  const currentMaxPosts =
    maxPosts ??
    String((config?.discovery_settings as Record<string, number> | null)?.max_posts ?? 50);

  const handleSave = useCallback(() => {
    const discoverySettings: Record<string, unknown> = {
      time_range: currentTimeRange,
      max_posts: parseInt(currentMaxPosts, 10) || 50,
    };

    upsertMutation.mutate(
      {
        search_keywords: currentSearchKeywords,
        target_subreddits: currentTargetSubreddits,
        banned_subreddits: currentBannedSubreddits,
        competitors: currentCompetitors,
        comment_instructions: currentCommentInstructions || null,
        niche_tags: currentNicheTags,
        discovery_settings: discoverySettings,
        is_active: currentIsActive,
      },
      {
        onSuccess: () => {
          setToastMessage('Reddit settings saved');
          setToastVariant('success');
          setShowToast(true);
          // Reset local edits so we re-derive from cache
          setIsActive(null);
          setSearchKeywords(null);
          setTargetSubreddits(null);
          setBannedSubreddits(null);
          setCompetitors(null);
          setCommentInstructions(null);
          setNicheTags(null);
          setTimeRange(null);
          setMaxPosts(null);
        },
        onError: (err) => {
          setToastMessage(err.message || 'Failed to save settings');
          setToastVariant('error');
          setShowToast(true);
        },
      },
    );
  }, [
    upsertMutation,
    currentSearchKeywords,
    currentTargetSubreddits,
    currentBannedSubreddits,
    currentCompetitors,
    currentCommentInstructions,
    currentNicheTags,
    currentTimeRange,
    currentMaxPosts,
    currentIsActive,
  ]);

  // Loading
  if (isLoading) {
    return (
      <div>
        <Link
          href={`/projects/${projectId}`}
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          Back to Project
        </Link>
        <LoadingSkeleton />
      </div>
    );
  }

  // Project not found
  if (projectError || !project) {
    return (
      <div>
        <Link
          href="/"
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          All Projects
        </Link>
        <div className="text-center py-12">
          <h1 className="text-2xl font-semibold text-warm-gray-900 mb-2">Project Not Found</h1>
          <p className="text-warm-gray-600 mb-6">
            The project you&apos;re looking for doesn&apos;t exist or has been deleted.
          </p>
          <Link href="/">
            <Button>Back to Dashboard</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Back link */}
      <Link
        href={`/projects/${projectId}`}
        className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
      >
        <BackArrowIcon className="w-4 h-4 mr-1" />
        Back to {project.name}
      </Link>

      {/* Header with toggle */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-warm-gray-900 mb-1">
            Reddit Settings
          </h1>
          <p className="text-warm-gray-500 text-sm">{project.name}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-warm-gray-600">
            {currentIsActive ? 'Active' : 'Inactive'}
          </span>
          <ToggleSwitch
            checked={currentIsActive}
            onChange={(val) => setIsActive(val)}
            label="Toggle Reddit engagement"
          />
        </div>
      </div>

      {/* Divider */}
      <hr className="border-cream-500 mb-6" />

      {/* Form */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm space-y-6">
        {/* Search Keywords */}
        <TagInput
          label="Search Keywords"
          tags={currentSearchKeywords}
          onChange={(val) => setSearchKeywords(val)}
          placeholder="Add keywords to monitor..."
        />

        {/* Target Subreddits */}
        <TagInput
          label="Target Subreddits"
          tags={currentTargetSubreddits}
          onChange={(val) => setTargetSubreddits(val)}
          placeholder="Add subreddits to engage in..."
          prefix="r/"
        />

        {/* Banned Subreddits */}
        <TagInput
          label="Banned Subreddits"
          tags={currentBannedSubreddits}
          onChange={(val) => setBannedSubreddits(val)}
          placeholder="Add subreddits to avoid..."
          prefix="r/"
        />

        {/* Competitors */}
        <TagInput
          label="Competitors"
          tags={currentCompetitors}
          onChange={(val) => setCompetitors(val)}
          placeholder="Add competitor names or domains..."
        />

        {/* Comment Instructions */}
        <div className="w-full">
          <label
            htmlFor="comment-instructions"
            className="block mb-1.5 text-sm font-medium text-warm-gray-700"
          >
            Comment Instructions
          </label>
          <textarea
            id="comment-instructions"
            rows={4}
            value={currentCommentInstructions}
            onChange={(e) => setCommentInstructions(e.target.value)}
            placeholder="Describe the voice, tone, and approach for Reddit comments..."
            className="block w-full px-4 py-2.5 text-warm-gray-900 bg-white border border-cream-400 rounded-sm transition-colors duration-150 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-palm-200 focus:ring-offset-1 focus:border-palm-400 hover:border-cream-500 resize-y"
          />
        </div>

        {/* Niche Tags */}
        <TagInput
          label="Niche Tags"
          tags={currentNicheTags}
          onChange={(val) => setNicheTags(val)}
          placeholder="Add niche or topic tags..."
        />

        {/* Discovery Settings */}
        <div>
          <h3 className="text-sm font-semibold text-warm-gray-900 mb-4">Discovery Settings</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Time Range */}
            <div>
              <label
                htmlFor="time-range"
                className="block mb-1.5 text-sm font-medium text-warm-gray-700"
              >
                Time Range
              </label>
              <select
                id="time-range"
                value={currentTimeRange}
                onChange={(e) => setTimeRange(e.target.value)}
                className="block w-full px-4 py-2.5 text-warm-gray-900 bg-white border border-cream-400 rounded-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-palm-200 focus:ring-offset-1 focus:border-palm-400 hover:border-cream-500"
              >
                {TIME_RANGE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Max Posts */}
            <div>
              <label
                htmlFor="max-posts"
                className="block mb-1.5 text-sm font-medium text-warm-gray-700"
              >
                Max Posts
              </label>
              <input
                id="max-posts"
                type="number"
                min={1}
                max={500}
                value={currentMaxPosts}
                onChange={(e) => setMaxPosts(e.target.value)}
                className="block w-full px-4 py-2.5 text-warm-gray-900 bg-white border border-cream-400 rounded-sm transition-colors duration-150 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-palm-200 focus:ring-offset-1 focus:border-palm-400 hover:border-cream-500"
              />
            </div>
          </div>
        </div>

        {/* Save button */}
        <div className="pt-2">
          <Button onClick={handleSave} disabled={upsertMutation.isPending}>
            {upsertMutation.isPending ? 'Saving...' : 'Save Settings'}
          </Button>
        </div>
      </div>

      {/* Toast */}
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
