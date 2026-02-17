'use client';

import { useState, useCallback, useMemo, type KeyboardEvent } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import {
  useRedditConfig,
  useUpsertRedditConfig,
  useTriggerDiscovery,
  useDiscoveryStatus,
  useRedditPosts,
  useUpdatePostStatus,
} from '@/hooks/useReddit';
import { Button, Toast, EmptyState } from '@/components/ui';
import type { RedditDiscoveredPost, DiscoveryStatus } from '@/lib/api';

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
// DISCOVERY ICONS
// =============================================================================

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6L9 17l-5-5" />
    </svg>
  );
}

function XCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M15 9l-6 6M9 9l6 6" />
    </svg>
  );
}

function ExternalLinkIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" />
    </svg>
  );
}

// =============================================================================
// INTENT BADGE COLORS
// =============================================================================

const INTENT_COLORS: Record<string, string> = {
  research: 'bg-lagoon-50 text-lagoon-700 border-lagoon-200',
  pain_point: 'bg-coral-50 text-coral-700 border-coral-200',
  competitor: 'bg-palm-50 text-palm-700 border-palm-200',
  question: 'bg-sand-100 text-warm-gray-700 border-sand-300',
  general: 'bg-cream-100 text-warm-gray-600 border-cream-300',
};

const INTENT_LABELS: Record<string, string> = {
  research: 'Research',
  pain_point: 'Pain Point',
  competitor: 'Competitor',
  question: 'Question',
  general: 'General',
};

function IntentBadge({ intent }: { intent: string }) {
  const colorClass = INTENT_COLORS[intent] || INTENT_COLORS.general;
  const label = INTENT_LABELS[intent] || intent;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm border ${colorClass}`}>
      {label}
    </span>
  );
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-warm-gray-400 text-sm">--</span>;
  const displayScore = score > 1 ? score : Math.round(score * 10);
  let colorClass = 'text-coral-600';
  if (displayScore >= 7) colorClass = 'text-palm-600 font-semibold';
  else if (displayScore >= 4) colorClass = 'text-amber-600';
  return <span className={`text-sm ${colorClass}`}>{displayScore}/10</span>;
}

// =============================================================================
// STATUS TAB OPTIONS
// =============================================================================

const STATUS_TABS = [
  { value: '', label: 'All' },
  { value: 'relevant', label: 'Relevant' },
  { value: 'irrelevant', label: 'Irrelevant' },
  { value: 'pending', label: 'Pending' },
] as const;

// =============================================================================
// DISCOVERY PROGRESS COMPONENT
// =============================================================================

function DiscoveryProgress({ status }: { status: DiscoveryStatus }) {
  const isActive = status.status === 'searching' || status.status === 'scoring' || status.status === 'storing';
  const isFailed = status.status === 'failed';
  const isComplete = status.status === 'complete';

  if (!isActive && !isFailed && !isComplete) return null;

  const phaseLabel =
    status.status === 'searching' ? 'Searching keywords...' :
    status.status === 'scoring' ? 'Scoring posts with AI...' :
    status.status === 'storing' ? 'Storing results...' :
    status.status === 'complete' ? 'Discovery complete' :
    status.status === 'failed' ? 'Discovery failed' : '';

  const progress = status.total_keywords > 0
    ? Math.round(((status.keywords_searched + status.posts_scored) / (status.total_keywords + status.total_posts_found || 1)) * 100)
    : 0;

  return (
    <div className={`rounded-sm border p-4 ${
      isFailed ? 'bg-coral-50 border-coral-200' :
      isComplete ? 'bg-palm-50 border-palm-200' :
      'bg-lagoon-50 border-lagoon-200'
    }`}>
      <div className="flex items-center gap-3 mb-2">
        {isActive && (
          <div className="w-4 h-4 border-2 border-lagoon-500 border-t-transparent rounded-full animate-spin" />
        )}
        {isComplete && <CheckIcon className="w-4 h-4 text-palm-600" />}
        {isFailed && <XCircleIcon className="w-4 h-4 text-coral-600" />}
        <span className={`text-sm font-medium ${
          isFailed ? 'text-coral-700' :
          isComplete ? 'text-palm-700' :
          'text-lagoon-700'
        }`}>
          {phaseLabel}
        </span>
      </div>

      {isActive && (
        <div className="w-full bg-white/50 rounded-full h-1.5 mb-2">
          <div
            className="bg-lagoon-500 h-1.5 rounded-full transition-all duration-500"
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
      )}

      <div className="flex gap-4 text-xs text-warm-gray-600">
        <span>Keywords: {status.keywords_searched}/{status.total_keywords}</span>
        <span>Posts found: {status.total_posts_found}</span>
        <span>Scored: {status.posts_scored}</span>
        {status.posts_stored > 0 && <span>Stored: {status.posts_stored}</span>}
      </div>

      {isFailed && status.error && (
        <p className="mt-2 text-xs text-coral-600">{status.error}</p>
      )}
    </div>
  );
}

// =============================================================================
// POSTS TABLE COMPONENT
// =============================================================================

function PostsTable({
  posts,
  onApprove,
  onReject,
}: {
  posts: RedditDiscoveredPost[];
  onApprove: (postId: string) => void;
  onReject: (postId: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-cream-300">
            <th className="text-left py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Subreddit</th>
            <th className="text-left py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Title</th>
            <th className="text-left py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Intent</th>
            <th className="text-left py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Score</th>
            <th className="text-left py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Status</th>
            <th className="text-left py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Discovered</th>
            <th className="text-right py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-cream-200">
          {posts.map((post) => (
            <tr key={post.id} className="hover:bg-cream-50 transition-colors">
              <td className="py-3 px-3">
                <span className="text-warm-gray-600 text-xs">r/{post.subreddit}</span>
              </td>
              <td className="py-3 px-3 max-w-md">
                <a
                  href={post.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-lagoon-600 hover:text-lagoon-800 hover:underline inline-flex items-center gap-1"
                >
                  <span className="line-clamp-2">{post.title}</span>
                  <ExternalLinkIcon className="w-3 h-3 flex-shrink-0" />
                </a>
              </td>
              <td className="py-3 px-3">
                <div className="flex flex-wrap gap-1">
                  {post.intent_categories && post.intent_categories.length > 0
                    ? post.intent_categories.map((intent) => (
                        <IntentBadge key={intent} intent={intent} />
                      ))
                    : post.intent
                      ? <IntentBadge intent={post.intent} />
                      : <span className="text-warm-gray-400 text-xs">--</span>
                  }
                </div>
              </td>
              <td className="py-3 px-3">
                <ScoreBadge score={post.relevance_score} />
              </td>
              <td className="py-3 px-3">
                <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm border ${
                  post.filter_status === 'relevant'
                    ? 'bg-palm-50 text-palm-700 border-palm-200'
                    : post.filter_status === 'irrelevant'
                      ? 'bg-coral-50 text-coral-600 border-coral-200'
                      : 'bg-cream-100 text-warm-gray-600 border-cream-300'
                }`}>
                  {post.filter_status}
                </span>
              </td>
              <td className="py-3 px-3 text-warm-gray-500 text-xs whitespace-nowrap">
                {new Date(post.discovered_at).toLocaleDateString()}
              </td>
              <td className="py-3 px-3">
                <div className="flex items-center justify-end gap-1">
                  <button
                    type="button"
                    onClick={() => onApprove(post.id)}
                    disabled={post.filter_status === 'relevant'}
                    className={`p-1.5 rounded-sm transition-colors ${
                      post.filter_status === 'relevant'
                        ? 'bg-palm-100 text-palm-600 cursor-default'
                        : 'text-warm-gray-400 hover:text-palm-600 hover:bg-palm-50'
                    }`}
                    aria-label={post.filter_status === 'relevant' ? 'Approved' : 'Approve post'}
                    title={post.filter_status === 'relevant' ? 'Already approved' : 'Mark as relevant'}
                  >
                    <CheckIcon className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onReject(post.id)}
                    disabled={post.filter_status === 'irrelevant'}
                    className={`p-1.5 rounded-sm transition-colors ${
                      post.filter_status === 'irrelevant'
                        ? 'bg-coral-100 text-coral-600 cursor-default'
                        : 'text-warm-gray-400 hover:text-coral-600 hover:bg-coral-50'
                    }`}
                    aria-label={post.filter_status === 'irrelevant' ? 'Rejected' : 'Reject post'}
                    title={post.filter_status === 'irrelevant' ? 'Already rejected' : 'Mark as irrelevant'}
                  >
                    <XCircleIcon className="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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
  const triggerDiscovery = useTriggerDiscovery(projectId);
  const { data: discoveryStatus } = useDiscoveryStatus(projectId);
  const updatePostStatus = useUpdatePostStatus(projectId);

  // Discovery filter state
  const [statusFilter, setStatusFilter] = useState('');
  const [intentFilter, setIntentFilter] = useState('');

  const postFilterParams = useMemo(() => {
    const params: { filter_status?: string; intent?: string } = {};
    if (statusFilter) params.filter_status = statusFilter;
    if (intentFilter) params.intent = intentFilter;
    return params;
  }, [statusFilter, intentFilter]);

  const { data: posts } = useRedditPosts(projectId, postFilterParams);
  // Unfiltered count to keep tabs visible when current filter yields 0
  const { data: allPosts } = useRedditPosts(projectId);

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

  // Track whether any form field has been edited but not saved
  const hasUnsavedChanges =
    isActive !== null ||
    searchKeywords !== null ||
    targetSubreddits !== null ||
    bannedSubreddits !== null ||
    competitors !== null ||
    commentInstructions !== null ||
    nicheTags !== null ||
    timeRange !== null ||
    maxPosts !== null;

  const buildSavePayload = useCallback(() => ({
    search_keywords: currentSearchKeywords,
    target_subreddits: currentTargetSubreddits,
    banned_subreddits: currentBannedSubreddits,
    competitors: currentCompetitors,
    comment_instructions: currentCommentInstructions || null,
    niche_tags: currentNicheTags,
    discovery_settings: {
      time_range: currentTimeRange,
      max_posts: parseInt(currentMaxPosts, 10) || 50,
    },
    is_active: currentIsActive,
  }), [
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

  const resetFormState = useCallback(() => {
    setIsActive(null);
    setSearchKeywords(null);
    setTargetSubreddits(null);
    setBannedSubreddits(null);
    setCompetitors(null);
    setCommentInstructions(null);
    setNicheTags(null);
    setTimeRange(null);
    setMaxPosts(null);
  }, []);

  const handleSave = useCallback(() => {
    upsertMutation.mutate(buildSavePayload(), {
      onSuccess: () => {
        setToastMessage('Reddit settings saved');
        setToastVariant('success');
        setShowToast(true);
        resetFormState();
      },
      onError: (err) => {
        setToastMessage(err.message || 'Failed to save settings');
        setToastVariant('error');
        setShowToast(true);
      },
    });
  }, [upsertMutation, buildSavePayload, resetFormState]);

  // Auto-save before triggering discovery if there are unsaved changes
  const handleDiscover = useCallback(() => {
    if (hasUnsavedChanges) {
      upsertMutation.mutate(buildSavePayload(), {
        onSuccess: () => {
          resetFormState();
          triggerDiscovery.mutate(currentTimeRange);
        },
        onError: (err) => {
          setToastMessage(err.message || 'Failed to save settings');
          setToastVariant('error');
          setShowToast(true);
        },
      });
    } else {
      triggerDiscovery.mutate(currentTimeRange);
    }
  }, [hasUnsavedChanges, upsertMutation, buildSavePayload, resetFormState, triggerDiscovery, currentTimeRange]);

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

      {/* ================================================================= */}
      {/* DISCOVERY SECTION (above settings) */}
      {/* ================================================================= */}

      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-warm-gray-900">Post Discovery</h2>
          <p className="text-sm text-warm-gray-500 mt-0.5">
            Search for relevant Reddit posts using your configured keywords
          </p>
        </div>
        <Button
          onClick={handleDiscover}
          disabled={
            triggerDiscovery.isPending ||
            upsertMutation.isPending ||
            (!existingConfig && !hasUnsavedChanges) ||
            currentSearchKeywords.length === 0 ||
            discoveryStatus?.status === 'searching' ||
            discoveryStatus?.status === 'scoring' ||
            discoveryStatus?.status === 'storing'
          }
          size="sm"
        >
          <SearchIcon className="w-4 h-4 mr-1.5" />
          {upsertMutation.isPending ? 'Saving...' : triggerDiscovery.isPending ? 'Starting...' : 'Discover Posts'}
        </Button>
      </div>

      {!existingConfig && (
        <p className="text-sm text-warm-gray-400 mb-4">
          Save your Reddit settings with at least one search keyword to enable discovery.
        </p>
      )}

      {/* Discovery Progress */}
      {discoveryStatus && discoveryStatus.status !== 'idle' && (
        <div className="mb-6">
          <DiscoveryProgress status={discoveryStatus} />
        </div>
      )}

      {/* Filter Controls — always visible when any posts exist */}
      {allPosts && allPosts.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 mb-4">
          {/* Status Tabs */}
          <div className="flex rounded-sm border border-cream-400 overflow-hidden">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.value}
                type="button"
                onClick={() => setStatusFilter(tab.value)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  statusFilter === tab.value
                    ? 'bg-palm-500 text-white'
                    : 'bg-white text-warm-gray-600 hover:bg-cream-100'
                } border-r border-cream-400 last:border-r-0`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Intent Filter */}
          <select
            value={intentFilter}
            onChange={(e) => setIntentFilter(e.target.value)}
            className="px-3 py-1.5 text-xs bg-white border border-cream-400 rounded-sm text-warm-gray-700 focus:outline-none focus:ring-2 focus:ring-palm-200 focus:border-palm-400"
          >
            <option value="">All Intents</option>
            <option value="research">Research</option>
            <option value="pain_point">Pain Point</option>
            <option value="competitor">Competitor</option>
            <option value="question">Question</option>
            <option value="general">General</option>
          </select>
        </div>
      )}

      {/* Posts Table or Empty State */}
      <div className="bg-white rounded-sm border border-cream-500 shadow-sm">
        {!posts || posts.length === 0 ? (
          (statusFilter || intentFilter) && allPosts && allPosts.length > 0 ? (
            <EmptyState
              icon={<SearchIcon className="w-10 h-10" />}
              title="No posts match this filter"
              description="Try a different filter or click 'All' to see all discovered posts."
            />
          ) : (
            <EmptyState
              icon={<SearchIcon className="w-10 h-10" />}
              title="No posts discovered yet"
              description={
                existingConfig && (existingConfig.search_keywords?.length ?? 0) > 0
                  ? 'Click "Discover Posts" to search for relevant Reddit threads.'
                  : 'Add search keywords in the settings below and save, then trigger discovery.'
              }
              action={
                existingConfig && (existingConfig.search_keywords?.length ?? 0) > 0 ? (
                  <Button
                    size="sm"
                    onClick={handleDiscover}
                    disabled={
                      triggerDiscovery.isPending ||
                      discoveryStatus?.status === 'searching' ||
                      discoveryStatus?.status === 'scoring' ||
                      discoveryStatus?.status === 'storing'
                    }
                  >
                    <SearchIcon className="w-4 h-4 mr-1.5" />
                    Discover Posts
                  </Button>
                ) : undefined
              }
            />
          )
        ) : (
          <PostsTable
            posts={posts}
            onApprove={(postId) =>
              updatePostStatus.mutate({ postId, data: { filter_status: 'relevant' } })
            }
            onReject={(postId) =>
              updatePostStatus.mutate({ postId, data: { filter_status: 'irrelevant' } })
            }
          />
        )}
      </div>

      {/* ================================================================= */}
      {/* SETTINGS SECTION */}
      {/* ================================================================= */}
      <hr className="border-cream-500 my-8" />

      <h2 className="text-lg font-semibold text-warm-gray-900 mb-4">Settings</h2>

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
