'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  useCommentQueue,
  useApproveComment,
  useRejectComment,
  useBulkApprove,
  useBulkReject,
} from '@/hooks/useReddit';
import { useProjects } from '@/hooks/use-projects';
import { Button, EmptyState, Toast } from '@/components/ui';
import type { RedditCommentResponse, CommentQueueParams } from '@/lib/api';

// =============================================================================
// ICONS
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

function PencilIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
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

function KeyboardIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" ry="2" />
      <path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M8 12h.01M12 12h.01M16 12h.01M7 16h10" />
    </svg>
  );
}

// =============================================================================
// HELPERS
// =============================================================================

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

// =============================================================================
// BADGE COMPONENTS
// =============================================================================

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

function PromotionalBadge({ isPromotional }: { isPromotional: boolean }) {
  return isPromotional ? (
    <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded-sm border bg-palm-50 text-palm-700 border-palm-200">
      Promo
    </span>
  ) : (
    <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded-sm border bg-lagoon-50 text-lagoon-700 border-lagoon-200">
      Organic
    </span>
  );
}

// Project name color rotation
const PROJECT_COLORS = [
  'bg-palm-50 text-palm-700 border-palm-200',
  'bg-lagoon-50 text-lagoon-700 border-lagoon-200',
  'bg-coral-50 text-coral-700 border-coral-200',
  'bg-sand-100 text-warm-gray-700 border-sand-300',
];

function ProjectBadge({ name, index }: { name: string; index: number }) {
  const colorClass = PROJECT_COLORS[index % PROJECT_COLORS.length];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-sm border ${colorClass}`}>
      {name}
    </span>
  );
}

// =============================================================================
// REJECT REASON PICKER
// =============================================================================

const REJECT_REASONS = [
  'Off-topic',
  'Too promotional',
  "Doesn't match voice",
  'Low quality',
  'Other',
];

function RejectPicker({
  onConfirm,
  onCancel,
}: {
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}) {
  const [customReason, setCustomReason] = useState('');
  const [showCustom, setShowCustom] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onCancel();
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [onCancel]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onCancel();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onCancel]);

  return (
    <div
      ref={ref}
      className="absolute bottom-full mb-2 right-0 bg-white border border-cream-500 rounded-sm shadow-lg p-2 w-56 z-10"
    >
      <p className="text-xs font-medium text-warm-gray-700 mb-2 px-1">Reject reason</p>
      {REJECT_REASONS.map((reason) => (
        <button
          key={reason}
          type="button"
          onClick={() => {
            if (reason === 'Other') {
              setShowCustom(true);
            } else {
              onConfirm(reason);
            }
          }}
          className="block w-full text-left px-2 py-1.5 text-sm text-warm-gray-700 hover:bg-cream-100 rounded-sm transition-colors"
        >
          {reason}
        </button>
      ))}
      {showCustom && (
        <div className="mt-2 space-y-1.5">
          <input
            type="text"
            value={customReason}
            onChange={(e) => setCustomReason(e.target.value)}
            placeholder="Enter reason..."
            autoFocus
            className="w-full px-2 py-1.5 text-sm border border-cream-400 rounded-sm focus:outline-none focus:ring-2 focus:ring-palm-200 focus:border-palm-400"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && customReason.trim()) {
                onConfirm(customReason.trim());
              }
            }}
          />
          <button
            type="button"
            onClick={() => {
              if (customReason.trim()) onConfirm(customReason.trim());
            }}
            disabled={!customReason.trim()}
            className="w-full px-2 py-1 text-xs font-medium text-white bg-coral-500 rounded-sm hover:bg-coral-600 transition-colors disabled:opacity-50"
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// COMMENT CARD (left panel)
// =============================================================================

function QueueCommentCard({
  comment,
  isSelected,
  isBulkSelected,
  onClick,
  onToggleBulk,
  projectName,
  projectIndex,
}: {
  comment: RedditCommentResponse;
  isSelected: boolean;
  isBulkSelected: boolean;
  onClick: () => void;
  onToggleBulk: () => void;
  projectName: string;
  projectIndex: number;
}) {
  return (
    <div
      onClick={onClick}
      className={`
        p-3 border-b border-cream-200 cursor-pointer transition-all duration-150
        ${isSelected ? 'ring-2 ring-palm-400 bg-palm-50/30' : 'hover:bg-cream-50'}
        ${isBulkSelected ? 'bg-lagoon-50/30' : ''}
      `}
    >
      {/* Top row: project badge + subreddit + timestamp */}
      <div className="flex items-center gap-2 mb-1.5">
        {comment.status === 'draft' && (
          <input
            type="checkbox"
            checked={isBulkSelected}
            onChange={(e) => {
              e.stopPropagation();
              onToggleBulk();
            }}
            onClick={(e) => e.stopPropagation()}
            className="rounded-sm border-cream-400 text-palm-500 focus:ring-palm-400 flex-shrink-0"
          />
        )}
        <ProjectBadge name={projectName} index={projectIndex} />
        {comment.post && (
          <span className="text-[10px] text-warm-gray-500">r/{comment.post.subreddit}</span>
        )}
        <span className="ml-auto text-[10px] text-warm-gray-400 flex-shrink-0">
          {formatRelativeTime(comment.created_at)}
        </span>
      </div>

      {/* Comment body truncated */}
      <p className="text-sm text-warm-gray-800 line-clamp-3 mb-1.5">
        {comment.body}
      </p>

      {/* Bottom row: badges */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <ApproachBadge approach={comment.approach_type} />
        <PromotionalBadge isPromotional={comment.is_promotional} />
      </div>
    </div>
  );
}

// =============================================================================
// POST CONTEXT PANEL (right panel)
// =============================================================================

function PostContextPanel({
  comment,
  projectName,
  projectIndex,
  isEditing,
  editBody,
  onStartEdit,
  onCancelEdit,
  onChangeEditBody,
  onApprove,
  onReject,
  isApproving,
  isRejecting,
}: {
  comment: RedditCommentResponse;
  projectName: string;
  projectIndex: number;
  isEditing: boolean;
  editBody: string;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onChangeEditBody: (body: string) => void;
  onApprove: (body?: string) => void;
  onReject: () => void;
  isApproving: boolean;
  isRejecting: boolean;
}) {
  const isDraft = comment.status === 'draft';
  const post = comment.post;

  return (
    <div className="h-full flex flex-col">
      {/* Post info */}
      {post && (
        <div className="p-4 border-b border-cream-200">
          <div className="flex items-center gap-2 mb-2">
            <ProjectBadge name={projectName} index={projectIndex} />
            <span className="text-xs text-warm-gray-500">r/{post.subreddit}</span>
          </div>
          <h3 className="text-sm font-medium text-warm-gray-900 mb-1">
            {post.title}
          </h3>
          {post.snippet && (
            <p className="text-xs text-warm-gray-500 line-clamp-3 mb-2">
              {post.snippet}
            </p>
          )}
          <a
            href={post.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-lagoon-600 hover:text-lagoon-800 hover:underline"
          >
            View on Reddit
            <ExternalLinkIcon className="w-3 h-3" />
          </a>
        </div>
      )}

      {/* Comment body */}
      <div className="flex-1 p-4 overflow-y-auto">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-medium text-warm-gray-500 uppercase tracking-wider">Comment</span>
          <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-sm border ${
            comment.status === 'draft' ? 'bg-sand-100 text-warm-gray-700 border-sand-300' :
            comment.status === 'approved' ? 'bg-palm-50 text-palm-700 border-palm-200' :
            comment.status === 'rejected' ? 'bg-coral-50 text-coral-600 border-coral-200' :
            'bg-cream-100 text-warm-gray-600 border-cream-300'
          }`}>
            {comment.status}
          </span>
        </div>

        {isEditing ? (
          <div className="space-y-2">
            <textarea
              value={editBody}
              onChange={(e) => onChangeEditBody(e.target.value)}
              rows={10}
              autoFocus
              className="block w-full px-3 py-2 text-sm text-warm-gray-900 bg-white border border-cream-400 rounded-sm transition-colors duration-150 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-palm-200 focus:ring-offset-1 focus:border-palm-400 resize-y"
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  e.preventDefault();
                  onApprove(editBody);
                }
                if (e.key === 'Escape') {
                  e.preventDefault();
                  onCancelEdit();
                }
              }}
            />
            <div className="flex items-center justify-between">
              <div className="text-xs text-warm-gray-400">
                {editBody.split(/\s+/).filter(Boolean).length} words | {editBody.length} chars
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onCancelEdit}
                  className="px-3 py-1 text-xs font-medium text-warm-gray-600 bg-sand-200 rounded-sm hover:bg-sand-300 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => onApprove(editBody)}
                  disabled={isApproving || !editBody.trim()}
                  className="px-3 py-1 text-xs font-medium text-white bg-palm-500 rounded-sm hover:bg-palm-600 transition-colors disabled:opacity-50"
                >
                  {isApproving ? 'Saving...' : 'Save & Approve'}
                </button>
              </div>
            </div>
            <p className="text-[10px] text-warm-gray-400">Cmd+Enter to save & approve, Escape to cancel</p>
          </div>
        ) : (
          <div className="text-sm text-warm-gray-800 whitespace-pre-wrap">
            {comment.body}
          </div>
        )}
      </div>

      {/* Action buttons */}
      {isDraft && !isEditing && (
        <div className="p-4 border-t border-cream-200 flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => onApprove()}
            disabled={isApproving}
          >
            <CheckIcon className="w-3.5 h-3.5 mr-1" />
            {isApproving ? 'Approving...' : 'Approve'}
          </Button>
          <button
            type="button"
            onClick={onStartEdit}
            className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-warm-gray-700 bg-sand-200 border border-sand-300 rounded-sm hover:bg-sand-300 transition-colors"
          >
            <PencilIcon className="w-3 h-3" />
            Edit
          </button>
          <div className="relative">
            <button
              type="button"
              onClick={onReject}
              disabled={isRejecting}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-coral-700 bg-coral-50 border border-coral-200 rounded-sm hover:bg-coral-100 transition-colors disabled:opacity-50"
            >
              <XCircleIcon className="w-3 h-3" />
              {isRejecting ? 'Rejecting...' : 'Reject'}
            </button>
          </div>
          <div className="ml-auto flex items-center gap-1 text-[10px] text-warm-gray-400">
            <KeyboardIcon className="w-3 h-3" />
            <span>j/k navigate | a approve | e edit | r reject</span>
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// LOADING SKELETON
// =============================================================================

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="flex items-center justify-between mb-6">
        <div className="h-7 bg-cream-300 rounded w-56" />
      </div>
      <div className="flex gap-3 mb-4">
        <div className="h-9 bg-cream-300 rounded w-24" />
        <div className="h-9 bg-cream-300 rounded w-24" />
        <div className="h-9 bg-cream-300 rounded w-24" />
        <div className="h-9 bg-cream-300 rounded w-24" />
      </div>
      <div className="flex gap-0 h-[calc(100vh-280px)]">
        <div className="w-3/5 bg-white border border-cream-500 rounded-sm">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="p-3 border-b border-cream-200">
              <div className="h-3 bg-cream-300 rounded w-24 mb-2" />
              <div className="h-4 bg-cream-300 rounded w-full mb-1" />
              <div className="h-4 bg-cream-300 rounded w-3/4" />
            </div>
          ))}
        </div>
        <div className="w-2/5 bg-white border border-cream-500 rounded-sm ml-4" />
      </div>
    </div>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

const STATUS_TABS = [
  { value: 'draft', label: 'Draft' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: '', label: 'All' },
] as const;

export default function CommentQueuePage() {
  // Filter state
  const [statusFilter, setStatusFilter] = useState<string>('draft');
  const [projectFilter, setProjectFilter] = useState<string>('');
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Selection state
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Edit state
  const [isEditing, setIsEditing] = useState(false);
  const [editBody, setEditBody] = useState('');

  // Reject picker state
  const [showRejectPicker, setShowRejectPicker] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<'single' | 'bulk'>('single');

  // Toast state
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');

  // Refs
  const listContainerRef = useRef<HTMLDivElement>(null);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchInput);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Build query params
  const queryParams = useMemo<CommentQueueParams>(() => {
    const params: CommentQueueParams = {};
    if (statusFilter) params.status = statusFilter;
    if (projectFilter) params.project_id = projectFilter;
    if (debouncedSearch) params.search = debouncedSearch;
    params.limit = 100;
    return params;
  }, [statusFilter, projectFilter, debouncedSearch]);

  // Data fetching
  const { data: queueData, isLoading } = useCommentQueue(queryParams);
  const { data: projectsData } = useProjects();
  const approveMutation = useApproveComment();
  const rejectMutation = useRejectComment();
  const bulkApproveMutation = useBulkApprove();
  const bulkRejectMutation = useBulkReject();

  const comments = queueData?.items ?? [];
  const counts = queueData?.counts ?? { draft: 0, approved: 0, rejected: 0, all: 0 };
  const projects = projectsData?.items ?? [];

  // Project lookup map
  const projectMap = useMemo(() => {
    const map = new Map<string, { name: string; index: number }>();
    projects.forEach((p, i) => map.set(p.id, { name: p.name, index: i }));
    return map;
  }, [projects]);

  // Currently selected comment
  const selectedComment = comments[selectedIndex] ?? null;

  // Reset selection when filters change
  useEffect(() => {
    setSelectedIndex(0);
    setSelectedIds(new Set());
    setIsEditing(false);
    setShowRejectPicker(false);
  }, [statusFilter, projectFilter, debouncedSearch]);

  // Toast helper
  const toast = useCallback((message: string, variant: 'success' | 'error') => {
    setToastMessage(message);
    setToastVariant(variant);
    setShowToast(true);
  }, []);

  // Auto-select next after approve/reject
  const selectNext = useCallback((currentIdx: number, listLength: number) => {
    if (listLength <= 1) {
      setSelectedIndex(0);
    } else if (currentIdx >= listLength - 1) {
      setSelectedIndex(Math.max(0, listLength - 2));
    }
    // else stays at same index (next item slides up)
  }, []);

  // Approve handler
  const handleApprove = useCallback((body?: string) => {
    if (!selectedComment) return;
    const projectId = selectedComment.project_id;
    const commentId = selectedComment.id;
    const listLen = comments.length;
    const curIdx = selectedIndex;

    approveMutation.mutate(
      { projectId, commentId, body },
      {
        onSuccess: () => {
          toast('Comment approved', 'success');
          setIsEditing(false);
          selectNext(curIdx, listLen);
        },
        onError: (err) => {
          toast(err.message || 'Failed to approve', 'error');
        },
      },
    );
  }, [selectedComment, comments.length, selectedIndex, approveMutation, toast, selectNext]);

  // Reject handler
  const handleReject = useCallback((reason: string) => {
    if (!selectedComment) return;
    const projectId = selectedComment.project_id;
    const commentId = selectedComment.id;
    const listLen = comments.length;
    const curIdx = selectedIndex;

    rejectMutation.mutate(
      { projectId, commentId, reason },
      {
        onSuccess: () => {
          toast('Comment rejected', 'success');
          setShowRejectPicker(false);
          selectNext(curIdx, listLen);
        },
        onError: (err) => {
          toast(err.message || 'Failed to reject', 'error');
        },
      },
    );
  }, [selectedComment, comments.length, selectedIndex, rejectMutation, toast, selectNext]);

  // Group selected comment IDs by project
  const groupByProject = useCallback(() => {
    const byProject = new Map<string, string[]>();
    for (const comment of comments) {
      if (selectedIds.has(comment.id)) {
        const existing = byProject.get(comment.project_id) || [];
        existing.push(comment.id);
        byProject.set(comment.project_id, existing);
      }
    }
    return byProject;
  }, [selectedIds, comments]);

  // Bulk approve handler — fires one request per project group
  const handleBulkApprove = useCallback(async () => {
    const byProject = groupByProject();
    if (byProject.size === 0) return;

    let totalApproved = 0;
    try {
      for (const [projectId, commentIds] of byProject) {
        const data = await bulkApproveMutation.mutateAsync({ projectId, commentIds });
        totalApproved += data.approved_count;
      }
      toast(`${totalApproved} comment${totalApproved !== 1 ? 's' : ''} approved`, 'success');
    } catch (err: any) {
      toast(err.message || 'Failed to bulk approve', 'error');
    }
    setSelectedIds(new Set());
    setSelectedIndex(0);
  }, [groupByProject, bulkApproveMutation, toast]);

  // Bulk reject handler — fires one request per project group
  const handleBulkReject = useCallback(async (reason: string) => {
    const byProject = groupByProject();
    if (byProject.size === 0) return;

    let totalRejected = 0;
    try {
      for (const [projectId, commentIds] of byProject) {
        const data = await bulkRejectMutation.mutateAsync({ projectId, commentIds, reason });
        totalRejected += data.rejected_count;
      }
      toast(`${totalRejected} comment${totalRejected !== 1 ? 's' : ''} rejected`, 'success');
    } catch (err: any) {
      toast(err.message || 'Failed to bulk reject', 'error');
    }
    setSelectedIds(new Set());
    setShowRejectPicker(false);
    setSelectedIndex(0);
  }, [groupByProject, bulkRejectMutation, toast]);

  // Toggle bulk selection
  const toggleBulkSelect = useCallback((commentId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(commentId)) next.delete(commentId);
      else next.add(commentId);
      return next;
    });
  }, []);

  // Scroll selected card into view
  useEffect(() => {
    if (listContainerRef.current) {
      const cards = listContainerRef.current.querySelectorAll('[data-comment-card]');
      const card = cards[selectedIndex] as HTMLElement | undefined;
      if (card) {
        card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }
  }, [selectedIndex]);

  // Keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const tag = (document.activeElement?.tagName || '').toUpperCase();
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      switch (e.key) {
        case 'j': {
          e.preventDefault();
          setSelectedIndex((prev) => Math.min(prev + 1, comments.length - 1));
          break;
        }
        case 'k': {
          e.preventDefault();
          setSelectedIndex((prev) => Math.max(prev - 1, 0));
          break;
        }
        case 'a': {
          if (selectedComment?.status === 'draft') {
            e.preventDefault();
            handleApprove();
          }
          break;
        }
        case 'e': {
          if (selectedComment?.status === 'draft') {
            e.preventDefault();
            setEditBody(selectedComment.body);
            setIsEditing(true);
          }
          break;
        }
        case 'r': {
          if (selectedComment?.status === 'draft') {
            e.preventDefault();
            setRejectTarget('single');
            setShowRejectPicker(true);
          }
          break;
        }
        case 'x': {
          if (selectedComment?.status === 'draft') {
            e.preventDefault();
            toggleBulkSelect(selectedComment.id);
          }
          break;
        }
        case 'Escape': {
          if (isEditing) {
            setIsEditing(false);
          } else if (showRejectPicker) {
            setShowRejectPicker(false);
          } else {
            setSelectedIndex(-1);
          }
          break;
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [comments.length, selectedComment, handleApprove, isEditing, showRejectPicker, toggleBulkSelect]);

  // Loading
  if (isLoading) {
    return <LoadingSkeleton />;
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold text-warm-gray-900">
          <span className="text-warm-gray-400">Reddit</span>
          <span className="text-warm-gray-300 mx-2">&rsaquo;</span>
          <span>Comment Queue</span>
        </h1>
      </div>

      {/* Status tabs */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex rounded-sm border border-cream-400 overflow-hidden">
          {STATUS_TABS.map((tab) => {
            const count = tab.value === 'draft' ? counts.draft
              : tab.value === 'approved' ? counts.approved
              : tab.value === 'rejected' ? counts.rejected
              : counts.all;
            return (
              <button
                key={tab.value}
                type="button"
                onClick={() => setStatusFilter(tab.value)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors flex items-center gap-1.5 ${
                  statusFilter === tab.value
                    ? 'bg-palm-500 text-white'
                    : 'bg-white text-warm-gray-600 hover:bg-cream-100'
                } border-r border-cream-400 last:border-r-0`}
              >
                {tab.label}
                <span className={`inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-semibold rounded-full ${
                  statusFilter === tab.value
                    ? 'bg-white/20 text-white'
                    : 'bg-cream-200 text-warm-gray-500'
                }`}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Project filter */}
        <select
          value={projectFilter}
          onChange={(e) => setProjectFilter(e.target.value)}
          className="h-8 px-3 pr-8 text-xs bg-white border border-cream-400 rounded-sm text-warm-gray-700 focus:outline-none focus:ring-2 focus:ring-palm-200 focus:border-palm-400 appearance-none cursor-pointer"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`,
            backgroundRepeat: 'no-repeat',
            backgroundPosition: 'right 8px center',
          }}
        >
          <option value="">All Projects</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>

        {/* Search input */}
        <div className="relative">
          <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-warm-gray-400" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search comments..."
            className="h-8 pl-8 pr-3 text-xs bg-white border border-cream-400 rounded-sm text-warm-gray-700 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-palm-200 focus:border-palm-400 w-48"
          />
        </div>
      </div>

      {/* Split view */}
      <div className="flex gap-4 h-[calc(100vh-260px)]">
        {/* Left panel: comment list */}
        <div className="w-3/5 bg-white rounded-sm border border-cream-500 shadow-sm overflow-hidden flex flex-col">
          {comments.length === 0 ? (
            <EmptyState
              icon={<MessageSquareIcon className="w-10 h-10" />}
              title="No comments to review"
              description={
                statusFilter
                  ? `No ${statusFilter} comments found. Try a different filter.`
                  : 'Comment queue is empty. Generate comments from project Reddit pages.'
              }
            />
          ) : (
            <div ref={listContainerRef} className="flex-1 overflow-y-auto">
              {comments.map((comment, index) => {
                const proj = projectMap.get(comment.project_id);
                return (
                  <div key={comment.id} data-comment-card>
                    <QueueCommentCard
                      comment={comment}
                      isSelected={index === selectedIndex}
                      isBulkSelected={selectedIds.has(comment.id)}
                      onClick={() => {
                        setSelectedIndex(index);
                        setIsEditing(false);
                        setShowRejectPicker(false);
                      }}
                      onToggleBulk={() => toggleBulkSelect(comment.id)}
                      projectName={proj?.name ?? 'Unknown'}
                      projectIndex={proj?.index ?? 0}
                    />
                  </div>
                );
              })}
            </div>
          )}

          {/* Bulk action bar */}
          {selectedIds.size > 0 && (
            <div className="border-t border-cream-300 bg-cream-50 px-4 py-2.5 flex items-center gap-3 relative">
              <span className="text-xs font-medium text-warm-gray-600">
                {selectedIds.size} selected
              </span>
              <Button
                size="sm"
                onClick={handleBulkApprove}
                disabled={bulkApproveMutation.isPending}
              >
                <CheckIcon className="w-3 h-3 mr-1" />
                Approve ({selectedIds.size})
              </Button>
              <button
                type="button"
                onClick={() => {
                  setRejectTarget('bulk');
                  setShowRejectPicker(true);
                }}
                disabled={bulkRejectMutation.isPending}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-coral-700 bg-coral-50 border border-coral-200 rounded-sm hover:bg-coral-100 transition-colors disabled:opacity-50"
              >
                <XCircleIcon className="w-3 h-3" />
                Reject ({selectedIds.size})
              </button>
              <button
                type="button"
                onClick={() => setSelectedIds(new Set())}
                className="ml-auto text-xs text-warm-gray-500 hover:text-warm-gray-700"
              >
                Clear
              </button>

              {showRejectPicker && rejectTarget === 'bulk' && (
                <RejectPicker
                  onConfirm={handleBulkReject}
                  onCancel={() => setShowRejectPicker(false)}
                />
              )}
            </div>
          )}
        </div>

        {/* Right panel: post context */}
        <div className="w-2/5 bg-white rounded-sm border border-cream-500 shadow-sm overflow-hidden relative">
          {selectedComment ? (
            <>
              <PostContextPanel
                comment={selectedComment}
                projectName={projectMap.get(selectedComment.project_id)?.name ?? 'Unknown'}
                projectIndex={projectMap.get(selectedComment.project_id)?.index ?? 0}
                isEditing={isEditing}
                editBody={editBody}
                onStartEdit={() => {
                  setEditBody(selectedComment.body);
                  setIsEditing(true);
                }}
                onCancelEdit={() => setIsEditing(false)}
                onChangeEditBody={setEditBody}
                onApprove={handleApprove}
                onReject={() => {
                  setRejectTarget('single');
                  setShowRejectPicker(true);
                }}
                isApproving={approveMutation.isPending}
                isRejecting={rejectMutation.isPending}
              />
              {showRejectPicker && rejectTarget === 'single' && (
                <div className="absolute bottom-16 right-4">
                  <RejectPicker
                    onConfirm={handleReject}
                    onCancel={() => setShowRejectPicker(false)}
                  />
                </div>
              )}
            </>
          ) : (
            <EmptyState
              icon={<MessageSquareIcon className="w-10 h-10" />}
              title="Select a comment to see details"
              description="Click on a comment in the list, or use j/k keys to navigate."
            />
          )}
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
