'use client';

import { useState, useCallback, useMemo, type KeyboardEvent } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useProject, useUpdateProject } from '@/hooks/use-projects';
import {
  useRedditConfig,
  useUpsertRedditConfig,
  useTriggerDiscovery,
  useDiscoveryStatus,
  useRedditPosts,
  useUpdatePostStatus,
  useComments,
  useGenerationStatus,
  useGenerateComment,
  useGenerateBatch,
  useUpdateComment,
  useDeleteComment,
  useRevertComment,
} from '@/hooks/useReddit';
import { Button, Toast, EmptyState } from '@/components/ui';
import type { RedditDiscoveredPost, RedditCommentResponse, DiscoveryStatus as DiscoveryStatusType, GenerationStatusResponse } from '@/lib/api';

// =============================================================================
// ICONS
// =============================================================================

function BackArrowIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  );
}

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

function SparklesIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l1.912 5.813a2 2 0 001.275 1.275L21 12l-5.813 1.912a2 2 0 00-1.275 1.275L12 21l-1.912-5.813a2 2 0 00-1.275-1.275L3 12l5.813-1.912a2 2 0 001.275-1.275L12 3z" />
    </svg>
  );
}

function MessageSquareIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  );
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 4v6h6M23 20v-6h-6" />
      <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15" />
    </svg>
  );
}

function PencilIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <div className={`border-2 border-current border-t-transparent rounded-full animate-spin ${className || 'w-4 h-4'}`} />
  );
}

// =============================================================================
// TAG INPUT
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
// LOADING SKELETON
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
// BADGES
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

const APPROACH_COLORS: Record<string, string> = {
  sandwich: 'bg-sand-100 text-warm-gray-700 border-sand-300',
  'story-based': 'bg-lagoon-50 text-lagoon-700 border-lagoon-200',
  'direct-help': 'bg-palm-50 text-palm-700 border-palm-200',
  comparison: 'bg-coral-50 text-coral-700 border-coral-200',
};

function ApproachBadge({ approach }: { approach: string | null }) {
  if (!approach) return null;
  const colorClass = APPROACH_COLORS[approach] || 'bg-cream-100 text-warm-gray-600 border-cream-300';
  const label = approach.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm border ${colorClass}`}>
      {label}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colorClass =
    status === 'draft' ? 'bg-sand-100 text-warm-gray-700 border-sand-300' :
    status === 'approved' ? 'bg-palm-50 text-palm-700 border-palm-200' :
    status === 'rejected' ? 'bg-coral-50 text-coral-600 border-coral-200' :
    'bg-cream-100 text-warm-gray-600 border-cream-300';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm border ${colorClass}`}>
      {status}
    </span>
  );
}

function PromotionalBadge({ isPromotional }: { isPromotional: boolean }) {
  return isPromotional ? (
    <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm border bg-palm-50 text-palm-700 border-palm-200">
      Promotional
    </span>
  ) : (
    <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm border bg-lagoon-50 text-lagoon-700 border-lagoon-200">
      Organic
    </span>
  );
}

// =============================================================================
// STATUS TABS & TIME RANGE
// =============================================================================

const STATUS_TABS = [
  { value: '', label: 'All' },
  { value: 'relevant', label: 'Relevant' },
  { value: 'irrelevant', label: 'Irrelevant' },
  { value: 'pending', label: 'Pending' },
] as const;

const TIME_RANGE_OPTIONS = [
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
];

// =============================================================================
// DISCOVERY PROGRESS
// =============================================================================

function DiscoveryProgress({ status }: { status: DiscoveryStatusType }) {
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
        {isActive && <div className="w-4 h-4 border-2 border-lagoon-500 border-t-transparent rounded-full animate-spin" />}
        {isComplete && <CheckIcon className="w-4 h-4 text-palm-600" />}
        {isFailed && <XCircleIcon className="w-4 h-4 text-coral-600" />}
        <span className={`text-sm font-medium ${
          isFailed ? 'text-coral-700' : isComplete ? 'text-palm-700' : 'text-lagoon-700'
        }`}>
          {phaseLabel}
        </span>
      </div>
      {isActive && (
        <div className="w-full bg-white/50 rounded-full h-1.5 mb-2">
          <div className="bg-lagoon-500 h-1.5 rounded-full transition-all duration-500" style={{ width: `${Math.min(progress, 100)}%` }} />
        </div>
      )}
      <div className="flex gap-4 text-xs text-warm-gray-600">
        <span>Keywords: {status.keywords_searched}/{status.total_keywords}</span>
        <span>Posts found: {status.total_posts_found}</span>
        <span>Scored: {status.posts_scored}</span>
        {status.posts_stored > 0 && <span>Stored: {status.posts_stored}</span>}
      </div>
      {isFailed && status.error && <p className="mt-2 text-xs text-coral-600">{status.error}</p>}
    </div>
  );
}

// =============================================================================
// GENERATION PROGRESS
// =============================================================================

function GenerationProgressBar({ status }: { status: GenerationStatusResponse }) {
  const isActive = status.status === 'generating';
  const isFailed = status.status === 'failed';
  const isComplete = status.status === 'complete';

  if (!isActive && !isFailed && !isComplete) return null;

  const progress = status.total_posts > 0
    ? Math.round((status.posts_generated / status.total_posts) * 100)
    : 0;

  return (
    <div className={`rounded-sm border p-4 ${
      isFailed ? 'bg-coral-50 border-coral-200' :
      isComplete ? 'bg-palm-50 border-palm-200' :
      'bg-lagoon-50 border-lagoon-200'
    }`}>
      <div className="flex items-center gap-3 mb-2">
        {isActive && <SpinnerIcon className="w-4 h-4 text-lagoon-500" />}
        {isComplete && <CheckIcon className="w-4 h-4 text-palm-600" />}
        {isFailed && <XCircleIcon className="w-4 h-4 text-coral-600" />}
        <span className={`text-sm font-medium ${
          isFailed ? 'text-coral-700' : isComplete ? 'text-palm-700' : 'text-lagoon-700'
        }`}>
          {isActive ? `Generating ${status.posts_generated}/${status.total_posts}...` :
           isComplete ? 'Generation complete' : 'Generation failed'}
        </span>
      </div>
      {isActive && (
        <div className="w-full bg-white/50 rounded-full h-1.5 mb-2">
          <div className="bg-lagoon-500 h-1.5 rounded-full transition-all duration-500" style={{ width: `${Math.min(progress, 100)}%` }} />
        </div>
      )}
      {isFailed && status.error && <p className="mt-1 text-xs text-coral-600">{status.error}</p>}
    </div>
  );
}

// =============================================================================
// POSTS TABLE
// =============================================================================

function PostsTable({
  posts, onApprove, onReject, onGenerate, generatingPostIds, commentsByPostId, selectedPostIds, onToggleSelect, onToggleSelectAll,
}: {
  posts: RedditDiscoveredPost[];
  onApprove: (postId: string) => void;
  onReject: (postId: string) => void;
  onGenerate?: (postId: string) => void;
  generatingPostIds?: Set<string>;
  commentsByPostId?: Map<string, RedditCommentResponse[]>;
  selectedPostIds: Set<string>;
  onToggleSelect: (postId: string) => void;
  onToggleSelectAll: () => void;
}) {
  const relevantPosts = posts.filter((p) => p.filter_status === 'relevant');
  const allRelevantSelected = relevantPosts.length > 0 && relevantPosts.every((p) => selectedPostIds.has(p.id));
  const someSelected = relevantPosts.some((p) => selectedPostIds.has(p.id));

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-cream-300">
            <th className="py-3 px-3 w-10">
              <input
                type="checkbox"
                checked={allRelevantSelected}
                ref={(el) => { if (el) el.indeterminate = someSelected && !allRelevantSelected; }}
                onChange={onToggleSelectAll}
                className="rounded-sm border-cream-400 text-palm-500 focus:ring-palm-400"
                title="Select all relevant posts"
              />
            </th>
            <th className="text-left py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Subreddit</th>
            <th className="text-left py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Title</th>
            <th className="text-left py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Intent</th>
            <th className="text-left py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Score</th>
            <th className="text-left py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Status</th>
            <th className="text-left py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Comment</th>
            <th className="text-right py-3 px-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-cream-200">
          {posts.map((post) => {
            const hasComment = commentsByPostId && commentsByPostId.has(post.id);
            const isGenerating = generatingPostIds?.has(post.id);
            const isRelevant = post.filter_status === 'relevant';
            const isSelected = selectedPostIds.has(post.id);

            return (
              <tr key={post.id} className={`hover:bg-cream-50 transition-colors ${isSelected ? 'bg-palm-50/30' : ''}`}>
                <td className="py-3 px-3">
                  {isRelevant ? (
                    <input type="checkbox" checked={isSelected} onChange={() => onToggleSelect(post.id)} className="rounded-sm border-cream-400 text-palm-500 focus:ring-palm-400" />
                  ) : <span className="block w-4" />}
                </td>
                <td className="py-3 px-3"><span className="text-warm-gray-600 text-xs">r/{post.subreddit}</span></td>
                <td className="py-3 px-3 max-w-md">
                  <a href={post.url} target="_blank" rel="noopener noreferrer" className="text-lagoon-600 hover:text-lagoon-800 hover:underline inline-flex items-center gap-1">
                    <span className="line-clamp-2">{post.title}</span>
                    <ExternalLinkIcon className="w-3 h-3 flex-shrink-0" />
                  </a>
                </td>
                <td className="py-3 px-3">
                  <div className="flex flex-wrap gap-1">
                    {post.intent_categories && post.intent_categories.length > 0
                      ? post.intent_categories.map((intent) => <IntentBadge key={intent} intent={intent} />)
                      : post.intent ? <IntentBadge intent={post.intent} /> : <span className="text-warm-gray-400 text-xs">--</span>}
                  </div>
                </td>
                <td className="py-3 px-3"><ScoreBadge score={post.relevance_score} /></td>
                <td className="py-3 px-3">
                  <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm border ${
                    post.filter_status === 'relevant' ? 'bg-palm-50 text-palm-700 border-palm-200' :
                    post.filter_status === 'irrelevant' ? 'bg-coral-50 text-coral-600 border-coral-200' :
                    'bg-cream-100 text-warm-gray-600 border-cream-300'
                  }`}>{post.filter_status}</span>
                </td>
                <td className="py-3 px-3">
                  {isGenerating ? <span className="inline-flex items-center gap-1 text-xs text-lagoon-600"><SpinnerIcon className="w-3 h-3" /> Generating...</span>
                   : hasComment ? <span className="inline-flex items-center gap-1 text-xs text-palm-600"><MessageSquareIcon className="w-3 h-3" /> Draft</span>
                   : isRelevant ? <span className="text-xs text-warm-gray-400">None</span> : null}
                </td>
                <td className="py-3 px-3">
                  <div className="flex items-center justify-end gap-1">
                    {isRelevant && onGenerate && (
                      <button type="button" onClick={() => onGenerate(post.id)} disabled={isGenerating} className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-palm-700 bg-palm-50 border border-palm-200 rounded-sm hover:bg-palm-100 transition-colors disabled:opacity-50" title={hasComment ? 'Regenerate comment' : 'Generate comment'}>
                        {isGenerating ? <SpinnerIcon className="w-3 h-3" /> : hasComment ? <RefreshIcon className="w-3 h-3" /> : <SparklesIcon className="w-3 h-3" />}
                        {hasComment ? 'Regen' : 'Generate'}
                      </button>
                    )}
                    <button type="button" onClick={() => onApprove(post.id)} disabled={post.filter_status === 'relevant'} className={`p-1.5 rounded-sm transition-colors ${post.filter_status === 'relevant' ? 'bg-palm-100 text-palm-600 cursor-default' : 'text-warm-gray-400 hover:text-palm-600 hover:bg-palm-50'}`} aria-label={post.filter_status === 'relevant' ? 'Approved' : 'Approve post'}>
                      <CheckIcon className="w-4 h-4" />
                    </button>
                    <button type="button" onClick={() => onReject(post.id)} disabled={post.filter_status === 'irrelevant'} className={`p-1.5 rounded-sm transition-colors ${post.filter_status === 'irrelevant' ? 'bg-coral-100 text-coral-600 cursor-default' : 'text-warm-gray-400 hover:text-coral-600 hover:bg-coral-50'}`} aria-label={post.filter_status === 'irrelevant' ? 'Rejected' : 'Reject post'}>
                      <XCircleIcon className="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// =============================================================================
// COMMENT CARD
// =============================================================================

function CommentCard({
  comment, onSaveEdit, onResetBody, onDelete, onRevert, isSaving,
}: {
  comment: RedditCommentResponse;
  onSaveEdit: (commentId: string, body: string) => void;
  onResetBody: (commentId: string) => void;
  onDelete: (commentId: string) => void;
  onRevert: (commentId: string) => void;
  isSaving: boolean;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editBody, setEditBody] = useState(comment.body);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const isDraft = comment.status === 'draft';
  const isEdited = comment.body !== comment.original_body;
  const postTitle = comment.post?.title ? (comment.post.title.length > 80 ? comment.post.title.slice(0, 80) + '...' : comment.post.title) : 'Unknown post';

  return (
    <div className="bg-white rounded-sm border border-cream-500 p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <StatusBadge status={comment.status} />
        <PromotionalBadge isPromotional={comment.is_promotional} />
        <ApproachBadge approach={comment.approach_type} />
        {isEdited && isDraft && <span className="text-xs text-warm-gray-400 italic">edited</span>}
      </div>
      {comment.post && (
        <div className="mb-3">
          <a href={comment.post.url} target="_blank" rel="noopener noreferrer" className="text-xs text-lagoon-600 hover:text-lagoon-800 hover:underline inline-flex items-center gap-1">
            <span className="text-warm-gray-500">r/{comment.post.subreddit}</span>
            <span className="mx-1 text-warm-gray-300">|</span>
            <span>{postTitle}</span>
            <ExternalLinkIcon className="w-3 h-3 flex-shrink-0" />
          </a>
        </div>
      )}
      {isEditing ? (
        <div className="space-y-2">
          <textarea value={editBody} onChange={(e) => setEditBody(e.target.value)} rows={6} className="block w-full px-3 py-2 text-sm text-warm-gray-900 bg-white border border-cream-400 rounded-sm transition-colors duration-150 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-palm-200 focus:ring-offset-1 focus:border-palm-400 resize-y" />
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => { if (editBody.trim() && editBody !== comment.body) onSaveEdit(comment.id, editBody.trim()); setIsEditing(false); }} disabled={isSaving || !editBody.trim() || editBody === comment.body} className="px-3 py-1 text-xs font-medium text-white bg-palm-500 rounded-sm hover:bg-palm-600 transition-colors disabled:opacity-50">{isSaving ? 'Saving...' : 'Save'}</button>
            <button type="button" onClick={() => { setEditBody(comment.body); setIsEditing(false); }} className="px-3 py-1 text-xs font-medium text-warm-gray-600 bg-sand-200 rounded-sm hover:bg-sand-300 transition-colors">Cancel</button>
          </div>
        </div>
      ) : (
        <div className={`text-sm text-warm-gray-800 whitespace-pre-wrap ${isDraft ? 'cursor-pointer hover:bg-cream-50 rounded-sm p-2 -m-2 transition-colors' : 'p-2 -m-2'}`} onClick={isDraft ? () => { setEditBody(comment.body); setIsEditing(true); } : undefined} title={isDraft ? 'Click to edit' : undefined}>
          {comment.body}
          {isDraft && !isEditing && <PencilIcon className="w-3 h-3 inline-block ml-2 text-warm-gray-400" />}
        </div>
      )}
      <div className="flex items-center justify-between mt-3 pt-2 border-t border-cream-200">
        <span className="text-xs text-warm-gray-400">{new Date(comment.created_at).toLocaleString()}</span>
        <div className="flex items-center gap-3">
          {isDraft && isEdited && !isEditing && (
            <button type="button" onClick={() => onResetBody(comment.id)} className="text-xs text-lagoon-600 hover:text-lagoon-800 hover:underline">Reset to original</button>
          )}
          {!isDraft && (
            <button type="button" onClick={() => onRevert(comment.id)} className="text-xs text-lagoon-600 hover:text-lagoon-800 hover:underline">Revert to draft</button>
          )}
          {!isEditing && !confirmDelete && (
            <button type="button" onClick={() => setConfirmDelete(true)} className="inline-flex items-center gap-1 text-xs text-warm-gray-400 hover:text-coral-600 transition-colors" title="Delete comment"><TrashIcon className="w-3 h-3" />Delete</button>
          )}
          {!isEditing && confirmDelete && (
            <span className="inline-flex items-center gap-2 text-xs">
              <button type="button" onClick={() => { onDelete(comment.id); setConfirmDelete(false); }} className="text-coral-600 font-medium hover:text-coral-700 transition-colors">Confirm delete?</button>
              <button type="button" onClick={() => setConfirmDelete(false)} className="text-warm-gray-400 hover:text-warm-gray-600 transition-colors">Cancel</button>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function RedditProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const updateProject = useUpdateProject();
  const { data: existingConfig, isLoading: isConfigLoading } = useRedditConfig(projectId);
  const upsertMutation = useUpsertRedditConfig(projectId);
  const triggerDiscovery = useTriggerDiscovery(projectId);
  const { data: discoveryStatus } = useDiscoveryStatus(projectId);
  const updatePostStatus = useUpdatePostStatus(projectId);

  const { data: comments } = useComments(projectId);
  const { data: generationStatus } = useGenerationStatus(projectId);
  const generateCommentMutation = useGenerateComment(projectId);
  const generateBatchMutation = useGenerateBatch(projectId);
  const updateCommentMutation = useUpdateComment(projectId);
  const deleteCommentMutation = useDeleteComment(projectId);
  const revertCommentMutation = useRevertComment(projectId);

  const [generatingPostIds, setGeneratingPostIds] = useState<Set<string>>(new Set());
  const [selectedPostIds, setSelectedPostIds] = useState<Set<string>>(new Set());

  const commentsByPostId = useMemo(() => {
    const map = new Map<string, RedditCommentResponse[]>();
    if (comments) {
      for (const comment of comments) {
        const existing = map.get(comment.post_id) || [];
        existing.push(comment);
        map.set(comment.post_id, existing);
      }
    }
    return map;
  }, [comments]);

  const [statusFilter, setStatusFilter] = useState('');
  const [intentFilter, setIntentFilter] = useState('');

  const postFilterParams = useMemo(() => {
    const params: { filter_status?: string; intent?: string } = {};
    if (statusFilter) params.filter_status = statusFilter;
    if (intentFilter) params.intent = intentFilter;
    return params;
  }, [statusFilter, intentFilter]);

  const { data: posts } = useRedditPosts(projectId, postFilterParams);
  const { data: allPosts } = useRedditPosts(projectId);

  const handleToggleSelect = useCallback((postId: string) => {
    setSelectedPostIds((prev) => { const next = new Set(prev); if (next.has(postId)) next.delete(postId); else next.add(postId); return next; });
  }, []);

  const handleToggleSelectAll = useCallback(() => {
    setSelectedPostIds((prev) => {
      const relevantIds = (posts || []).filter((p) => p.filter_status === 'relevant').map((p) => p.id);
      const allSelected = relevantIds.length > 0 && relevantIds.every((id) => prev.has(id));
      if (allSelected) return new Set();
      return new Set(relevantIds);
    });
  }, [posts]);

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

  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');

  const isLoading = isProjectLoading || isConfigLoading;
  const config = existingConfig ?? null;

  const currentIsActive = isActive ?? config?.is_active ?? true;
  const currentSearchKeywords = useMemo(() => searchKeywords ?? config?.search_keywords ?? [], [searchKeywords, config?.search_keywords]);
  const currentTargetSubreddits = useMemo(() => targetSubreddits ?? config?.target_subreddits ?? [], [targetSubreddits, config?.target_subreddits]);
  const currentBannedSubreddits = useMemo(() => bannedSubreddits ?? config?.banned_subreddits ?? [], [bannedSubreddits, config?.banned_subreddits]);
  const currentCompetitors = useMemo(() => competitors ?? config?.competitors ?? [], [competitors, config?.competitors]);
  const currentCommentInstructions = commentInstructions ?? config?.comment_instructions ?? '';
  const currentNicheTags = useMemo(() => nicheTags ?? config?.niche_tags ?? [], [nicheTags, config?.niche_tags]);
  const currentTimeRange = timeRange ?? (config?.discovery_settings as Record<string, string> | null)?.time_range ?? '7d';
  const currentMaxPosts = maxPosts ?? String((config?.discovery_settings as Record<string, number> | null)?.max_posts ?? 50);

  const hasUnsavedChanges = isActive !== null || searchKeywords !== null || targetSubreddits !== null || bannedSubreddits !== null || competitors !== null || commentInstructions !== null || nicheTags !== null || timeRange !== null || maxPosts !== null;

  const buildSavePayload = useCallback(() => ({
    search_keywords: currentSearchKeywords,
    target_subreddits: currentTargetSubreddits,
    banned_subreddits: currentBannedSubreddits,
    competitors: currentCompetitors,
    comment_instructions: currentCommentInstructions || null,
    niche_tags: currentNicheTags,
    discovery_settings: { time_range: currentTimeRange, max_posts: parseInt(currentMaxPosts, 10) || 50 },
    is_active: currentIsActive,
  }), [currentSearchKeywords, currentTargetSubreddits, currentBannedSubreddits, currentCompetitors, currentCommentInstructions, currentNicheTags, currentTimeRange, currentMaxPosts, currentIsActive]);

  const resetFormState = useCallback(() => {
    setIsActive(null); setSearchKeywords(null); setTargetSubreddits(null); setBannedSubreddits(null);
    setCompetitors(null); setCommentInstructions(null); setNicheTags(null); setTimeRange(null); setMaxPosts(null);
  }, []);

  const handleSave = useCallback(() => {
    upsertMutation.mutate(buildSavePayload(), {
      onSuccess: () => { setToastMessage('Reddit settings saved'); setToastVariant('success'); setShowToast(true); resetFormState(); },
      onError: (err) => { setToastMessage(err.message || 'Failed to save settings'); setToastVariant('error'); setShowToast(true); },
    });
  }, [upsertMutation, buildSavePayload, resetFormState]);

  const handleDiscover = useCallback(() => {
    if (hasUnsavedChanges) {
      upsertMutation.mutate(buildSavePayload(), {
        onSuccess: () => { resetFormState(); triggerDiscovery.mutate(currentTimeRange); },
        onError: (err) => { setToastMessage(err.message || 'Failed to save settings'); setToastVariant('error'); setShowToast(true); },
      });
    } else {
      triggerDiscovery.mutate(currentTimeRange);
    }
  }, [hasUnsavedChanges, upsertMutation, buildSavePayload, resetFormState, triggerDiscovery, currentTimeRange]);

  const handleGenerateComment = useCallback((postId: string) => {
    setGeneratingPostIds((prev) => new Set(prev).add(postId));
    generateCommentMutation.mutate({ postId }, {
      onSuccess: () => { setToastMessage('Comment generated'); setToastVariant('success'); setShowToast(true); setGeneratingPostIds((prev) => { const next = new Set(prev); next.delete(postId); return next; }); },
      onError: (err) => { setToastMessage(err.message || 'Failed to generate comment'); setToastVariant('error'); setShowToast(true); setGeneratingPostIds((prev) => { const next = new Set(prev); next.delete(postId); return next; }); },
    });
  }, [generateCommentMutation]);

  const handleBatchGenerate = useCallback(() => {
    const postIds = selectedPostIds.size > 0 ? Array.from(selectedPostIds) : undefined;
    generateBatchMutation.mutate(postIds, {
      onSuccess: () => { setToastMessage('Batch generation started'); setToastVariant('success'); setShowToast(true); setSelectedPostIds(new Set()); },
      onError: (err) => { setToastMessage(err.message || 'Failed to start batch generation'); setToastVariant('error'); setShowToast(true); },
    });
  }, [generateBatchMutation, selectedPostIds]);

  const handleSaveCommentEdit = useCallback((commentId: string, body: string) => {
    updateCommentMutation.mutate({ commentId, data: { body } }, {
      onSuccess: () => { setToastMessage('Comment updated'); setToastVariant('success'); setShowToast(true); },
      onError: (err) => { setToastMessage(err.message || 'Failed to update comment'); setToastVariant('error'); setShowToast(true); },
    });
  }, [updateCommentMutation]);

  const handleResetCommentBody = useCallback((commentId: string) => {
    const comment = comments?.find((c) => c.id === commentId);
    if (comment) {
      updateCommentMutation.mutate({ commentId, data: { body: comment.original_body } }, {
        onSuccess: () => { setToastMessage('Comment reset to original'); setToastVariant('success'); setShowToast(true); },
        onError: (err) => { setToastMessage(err.message || 'Failed to reset comment'); setToastVariant('error'); setShowToast(true); },
      });
    }
  }, [updateCommentMutation, comments]);

  const handleDeleteComment = useCallback((commentId: string) => {
    deleteCommentMutation.mutate(commentId, {
      onSuccess: () => { setToastMessage('Comment deleted'); setToastVariant('success'); setShowToast(true); },
      onError: (err) => { setToastMessage(err.message || 'Failed to delete comment'); setToastVariant('error'); setShowToast(true); },
    });
  }, [deleteCommentMutation]);

  const handleRevertComment = useCallback((commentId: string) => {
    revertCommentMutation.mutate(commentId, {
      onSuccess: () => { setToastMessage('Comment reverted to draft'); setToastVariant('success'); setShowToast(true); },
      onError: (err) => { setToastMessage(err.message || 'Failed to revert comment'); setToastVariant('error'); setShowToast(true); },
    });
  }, [revertCommentMutation]);

  const isGenerationActive = generationStatus?.status === 'generating';

  if (isLoading) {
    return (
      <div>
        <Link href="/reddit" className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm">
          <BackArrowIcon className="w-4 h-4 mr-1" />
          Reddit Projects
        </Link>
        <LoadingSkeleton />
      </div>
    );
  }

  if (projectError || !project) {
    return (
      <div>
        <Link href="/reddit" className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm">
          <BackArrowIcon className="w-4 h-4 mr-1" />
          Reddit Projects
        </Link>
        <div className="text-center py-12">
          <h1 className="text-2xl font-semibold text-warm-gray-900 mb-2">Project Not Found</h1>
          <p className="text-warm-gray-600 mb-6">The project you&apos;re looking for doesn&apos;t exist or has been deleted.</p>
          <Link href="/reddit"><Button>Back to Reddit Projects</Button></Link>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Back link */}
      <Link href="/reddit" className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm">
        <BackArrowIcon className="w-4 h-4 mr-1" />
        Reddit Projects
      </Link>

      {/* Header with toggle */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-warm-gray-900 mb-1">Reddit Settings</h1>
          <p className="text-warm-gray-500 text-sm">{project.name}</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-warm-gray-600">{currentIsActive ? 'Active' : 'Inactive'}</span>
          <ToggleSwitch checked={currentIsActive} onChange={(val) => setIsActive(val)} label="Toggle Reddit engagement" />
        </div>
      </div>

      <hr className="border-cream-500 mb-6" />

      {/* DISCOVERY SECTION */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-warm-gray-900">Post Discovery</h2>
          <p className="text-sm text-warm-gray-500 mt-0.5">Search for relevant Reddit posts using your configured keywords</p>
        </div>
        <Button onClick={handleDiscover} disabled={triggerDiscovery.isPending || upsertMutation.isPending || (!existingConfig && !hasUnsavedChanges) || currentSearchKeywords.length === 0 || discoveryStatus?.status === 'searching' || discoveryStatus?.status === 'scoring' || discoveryStatus?.status === 'storing'} size="sm">
          <SearchIcon className="w-4 h-4 mr-1.5" />
          {upsertMutation.isPending ? 'Saving...' : triggerDiscovery.isPending ? 'Starting...' : 'Discover Posts'}
        </Button>
      </div>

      {!existingConfig && <p className="text-sm text-warm-gray-400 mb-4">Save your Reddit settings with at least one search keyword to enable discovery.</p>}

      {discoveryStatus && discoveryStatus.status !== 'idle' && (
        <div className="mb-6"><DiscoveryProgress status={discoveryStatus} /></div>
      )}

      {allPosts && allPosts.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <div className="flex rounded-sm border border-cream-400 overflow-hidden">
            {STATUS_TABS.map((tab) => (
              <button key={tab.value} type="button" onClick={() => setStatusFilter(tab.value)} className={`px-3 py-1.5 text-xs font-medium transition-colors ${statusFilter === tab.value ? 'bg-palm-500 text-white' : 'bg-white text-warm-gray-600 hover:bg-cream-100'} border-r border-cream-400 last:border-r-0`}>
                {tab.label}
              </button>
            ))}
          </div>
          <select value={intentFilter} onChange={(e) => setIntentFilter(e.target.value)} className="px-3 py-1.5 text-xs bg-white border border-cream-400 rounded-sm text-warm-gray-700 focus:outline-none focus:ring-2 focus:ring-palm-200 focus:border-palm-400">
            <option value="">All Intents</option>
            <option value="research">Research</option>
            <option value="pain_point">Pain Point</option>
            <option value="competitor">Competitor</option>
            <option value="question">Question</option>
            <option value="general">General</option>
          </select>
          <div className="flex-1" />
          <Button onClick={handleBatchGenerate} disabled={generateBatchMutation.isPending || isGenerationActive || selectedPostIds.size === 0} size="sm">
            <SparklesIcon className="w-4 h-4 mr-1.5" />
            {generateBatchMutation.isPending ? 'Starting...' : isGenerationActive ? 'Generating...' : selectedPostIds.size > 0 ? `Generate Comments (${selectedPostIds.size})` : 'Generate Comments'}
          </Button>
        </div>
      )}

      {generationStatus && generationStatus.status !== 'idle' && (
        <div className="mb-4"><GenerationProgressBar status={generationStatus} /></div>
      )}

      <div className="bg-white rounded-sm border border-cream-500 shadow-sm">
        {!posts || posts.length === 0 ? (
          (statusFilter || intentFilter) && allPosts && allPosts.length > 0 ? (
            <EmptyState icon={<SearchIcon className="w-10 h-10" />} title="No posts match this filter" description="Try a different filter or click 'All' to see all discovered posts." />
          ) : (
            <EmptyState icon={<SearchIcon className="w-10 h-10" />} title="No posts discovered yet" description={existingConfig && (existingConfig.search_keywords?.length ?? 0) > 0 ? 'Click "Discover Posts" to search for relevant Reddit threads.' : 'Add search keywords in the settings below and save, then trigger discovery.'} action={existingConfig && (existingConfig.search_keywords?.length ?? 0) > 0 ? <Button size="sm" onClick={handleDiscover} disabled={triggerDiscovery.isPending || discoveryStatus?.status === 'searching' || discoveryStatus?.status === 'scoring' || discoveryStatus?.status === 'storing'}><SearchIcon className="w-4 h-4 mr-1.5" />Discover Posts</Button> : undefined} />
          )
        ) : (
          <PostsTable posts={posts} onApprove={(postId) => updatePostStatus.mutate({ postId, data: { filter_status: 'relevant' } })} onReject={(postId) => updatePostStatus.mutate({ postId, data: { filter_status: 'irrelevant' } })} onGenerate={handleGenerateComment} generatingPostIds={generatingPostIds} commentsByPostId={commentsByPostId} selectedPostIds={selectedPostIds} onToggleSelect={handleToggleSelect} onToggleSelectAll={handleToggleSelectAll} />
        )}
      </div>

      {comments && comments.length > 0 && (
        <div className="mt-6">
          <div className="flex items-center gap-2 mb-3">
            <MessageSquareIcon className="w-4 h-4 text-warm-gray-500" />
            <span className="text-sm font-medium text-warm-gray-700">{comments.length} comment{comments.length !== 1 ? 's' : ''} generated</span>
          </div>
          <div className="space-y-3">
            {comments.map((comment) => (
              <CommentCard key={comment.id} comment={comment} onSaveEdit={handleSaveCommentEdit} onResetBody={handleResetCommentBody} onDelete={handleDeleteComment} onRevert={handleRevertComment} isSaving={updateCommentMutation.isPending} />
            ))}
          </div>
        </div>
      )}

      {/* SETTINGS SECTION */}
      <hr className="border-cream-500 my-8" />
      <h2 className="text-lg font-semibold text-warm-gray-900 mb-4">Settings</h2>

      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm space-y-6">
        <TagInput label="Search Keywords" tags={currentSearchKeywords} onChange={(val) => setSearchKeywords(val)} placeholder="Add keywords to monitor..." />
        <TagInput label="Target Subreddits" tags={currentTargetSubreddits} onChange={(val) => setTargetSubreddits(val)} placeholder="Add subreddits to engage in..." prefix="r/" />
        <TagInput label="Banned Subreddits" tags={currentBannedSubreddits} onChange={(val) => setBannedSubreddits(val)} placeholder="Add subreddits to avoid..." prefix="r/" />
        <TagInput label="Competitors" tags={currentCompetitors} onChange={(val) => setCompetitors(val)} placeholder="Add competitor names or domains..." />
        <div className="w-full">
          <label htmlFor="comment-instructions" className="block mb-1.5 text-sm font-medium text-warm-gray-700">Comment Instructions</label>
          <textarea id="comment-instructions" rows={4} value={currentCommentInstructions} onChange={(e) => setCommentInstructions(e.target.value)} placeholder="Describe the voice, tone, and approach for Reddit comments..." className="block w-full px-4 py-2.5 text-warm-gray-900 bg-white border border-cream-400 rounded-sm transition-colors duration-150 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-palm-200 focus:ring-offset-1 focus:border-palm-400 hover:border-cream-500 resize-y" />
        </div>
        <TagInput label="Niche Tags" tags={currentNicheTags} onChange={(val) => setNicheTags(val)} placeholder="Add niche or topic tags..." />
        <div>
          <h3 className="text-sm font-semibold text-warm-gray-900 mb-4">Discovery Settings</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="time-range" className="block mb-1.5 text-sm font-medium text-warm-gray-700">Time Range</label>
              <select id="time-range" value={currentTimeRange} onChange={(e) => setTimeRange(e.target.value)} className="block w-full px-4 py-2.5 text-warm-gray-900 bg-white border border-cream-400 rounded-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-palm-200 focus:ring-offset-1 focus:border-palm-400 hover:border-cream-500">
                {TIME_RANGE_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="max-posts" className="block mb-1.5 text-sm font-medium text-warm-gray-700">Max Posts</label>
              <input id="max-posts" type="number" min={1} max={500} value={currentMaxPosts} onChange={(e) => setMaxPosts(e.target.value)} className="block w-full px-4 py-2.5 text-warm-gray-900 bg-white border border-cream-400 rounded-sm transition-colors duration-150 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-palm-200 focus:ring-offset-1 focus:border-palm-400 hover:border-cream-500" />
            </div>
          </div>
        </div>
        <div className="pt-2">
          <Button onClick={handleSave} disabled={upsertMutation.isPending}>
            {upsertMutation.isPending ? 'Saving...' : 'Save Settings'}
          </Button>
        </div>
      </div>

      {/* AI SEO Project section */}
      <hr className="border-cream-500 my-6" />
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
        <div className="flex items-center gap-3 mb-3">
          <svg className="w-5 h-5 text-palm-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
          <h2 className="text-lg font-semibold text-warm-gray-900">AI SEO</h2>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            project.reddit_only
              ? 'bg-cream-100 text-warm-gray-600'
              : 'bg-palm-50 text-palm-700'
          }`}>
            {project.reddit_only ? 'Not configured' : 'Configured'}
          </span>
        </div>
        <p className="text-warm-gray-600 text-sm mb-4">
          {project.reddit_only
            ? 'Enable AI SEO to optimize existing pages and generate new content for this project'
            : 'This project is also set up for AI SEO content optimization'}
        </p>
        {project.reddit_only ? (
          <Button
            onClick={() => {
              updateProject.mutate(
                { id: projectId, data: { reddit_only: false } },
                {
                  onSuccess: () => router.push(`/projects/${projectId}`),
                  onError: () => router.push(`/projects/${projectId}`),
                }
              );
            }}
            disabled={updateProject.isPending}
          >
            {updateProject.isPending ? 'Setting up...' : 'Set up AI SEO'}
          </Button>
        ) : (
          <Link href={`/projects/${projectId}`}>
            <Button variant="secondary">View AI SEO Project</Button>
          </Link>
        )}
      </div>

      {showToast && <Toast message={toastMessage} variant={toastVariant} onClose={() => setShowToast(false)} />}
    </div>
  );
}
