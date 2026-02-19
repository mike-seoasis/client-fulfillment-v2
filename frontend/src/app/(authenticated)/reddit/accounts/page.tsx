'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  useRedditAccounts,
  useCreateRedditAccount,
  useDeleteRedditAccount,
} from '@/hooks/useReddit';
import { Button, EmptyState, Input, Textarea, Toast } from '@/components/ui';
import type { RedditAccount } from '@/lib/api';

// =============================================================================
// CONSTANTS
// =============================================================================

const WARMUP_STAGES = [
  { value: 'observation', label: 'Observation' },
  { value: 'light_engagement', label: 'Light Engagement' },
  { value: 'regular_activity', label: 'Regular Activity' },
  { value: 'operational', label: 'Operational' },
];

const ACCOUNT_STATUSES = [
  { value: 'active', label: 'Active' },
  { value: 'warming_up', label: 'Warming Up' },
  { value: 'cooldown', label: 'Cooldown' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'banned', label: 'Banned' },
];

// =============================================================================
// HELPERS
// =============================================================================

function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return '—';
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

function formatCooldown(dateString: string | null): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  if (diffMs <= 0) return 'expired';
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  if (diffMins < 60) return `${diffMins}m left`;
  if (diffHours < 24) return `${diffHours}h left`;
  return `${Math.floor(diffHours / 24)}d left`;
}

function getStatusBadgeClasses(status: string): string {
  switch (status) {
    case 'active':
      return 'bg-palm-50 text-palm-700 border-palm-200';
    case 'warming_up':
      return 'bg-lagoon-50 text-lagoon-700 border-lagoon-200';
    case 'cooldown':
      return 'bg-cream-100 text-warm-gray-600 border-cream-300';
    case 'suspended':
      return 'bg-coral-50 text-coral-700 border-coral-200';
    case 'banned':
      return 'bg-coral-100 text-coral-800 border-coral-300';
    default:
      return 'bg-cream-100 text-warm-gray-600 border-cream-300';
  }
}

function formatStatusLabel(status: string): string {
  return ACCOUNT_STATUSES.find((s) => s.value === status)?.label ?? status;
}

function formatWarmupLabel(stage: string): string {
  return WARMUP_STAGES.find((s) => s.value === stage)?.label ?? stage;
}

// =============================================================================
// UNIQUE NICHES EXTRACTION
// =============================================================================

function extractUniqueNiches(accounts: RedditAccount[]): string[] {
  const niches = new Set<string>();
  for (const account of accounts) {
    for (const tag of account.niche_tags) {
      niches.add(tag);
    }
  }
  return Array.from(niches).sort();
}

// =============================================================================
// LOADING SKELETON
// =============================================================================

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      {/* Header skeleton */}
      <div className="flex items-center justify-between mb-6">
        <div className="h-7 bg-cream-300 rounded w-56" />
        <div className="h-9 bg-cream-300 rounded w-32" />
      </div>
      {/* Filter bar skeleton */}
      <div className="flex gap-3 mb-4">
        <div className="h-9 bg-cream-300 rounded w-36" />
        <div className="h-9 bg-cream-300 rounded w-36" />
        <div className="h-9 bg-cream-300 rounded w-36" />
      </div>
      {/* Table skeleton */}
      <div className="bg-white rounded-sm border border-cream-500 overflow-hidden">
        <div className="h-10 bg-cream-100 border-b border-cream-300" />
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-14 border-b border-cream-200 px-4 flex items-center gap-4">
            <div className="h-4 bg-cream-300 rounded w-28" />
            <div className="h-5 bg-cream-300 rounded w-16" />
            <div className="h-4 bg-cream-300 rounded w-24" />
            <div className="h-5 bg-cream-300 rounded w-20" />
            <div className="h-4 bg-cream-300 rounded w-16" />
            <div className="h-4 bg-cream-300 rounded w-16" />
            <div className="h-4 bg-cream-300 rounded w-16" />
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// FILTER SELECT
// =============================================================================

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="h-9 px-3 pr-8 text-sm bg-white border border-cream-400 rounded-sm text-warm-gray-700 hover:border-cream-500 focus:outline-none focus:ring-2 focus:ring-palm-200 focus:border-palm-400 appearance-none cursor-pointer"
      style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`,
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'right 8px center',
      }}
    >
      <option value="">{label}</option>
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

// =============================================================================
// ADD ACCOUNT MODAL
// =============================================================================

function AddAccountModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const [username, setUsername] = useState('');
  const [nicheTags, setNicheTags] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');
  const createAccount = useCreateRedditAccount();
  const modalRef = useRef<HTMLDivElement>(null);

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setUsername('');
      setNicheTags('');
      setNotes('');
      setError('');
    }
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Close on backdrop click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
      onClose();
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedUsername = username.trim();
    if (!trimmedUsername) {
      setError('Username is required');
      return;
    }

    const tags = nicheTags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);

    createAccount.mutate(
      {
        username: trimmedUsername,
        niche_tags: tags.length > 0 ? tags : undefined,
        notes: notes.trim() || null,
      },
      {
        onSuccess: () => {
          onClose();
        },
        onError: (err) => {
          setError(err.message || 'Failed to create account');
        },
      },
    );
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={handleBackdropClick}
    >
      <div
        ref={modalRef}
        className="bg-white rounded-sm border border-cream-500 shadow-xl w-full max-w-md mx-4 p-6"
      >
        <h2 className="text-lg font-semibold text-warm-gray-900 mb-4">
          Add Reddit Account
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Username"
            placeholder="e.g. cool_redditor_42"
            value={username}
            onChange={(e) => {
              setUsername(e.target.value);
              if (error) setError('');
            }}
            error={error && !username.trim() ? 'Username is required' : undefined}
            required
          />
          <Input
            label="Niche Tags"
            placeholder="e.g. fitness, nutrition, health"
            value={nicheTags}
            onChange={(e) => setNicheTags(e.target.value)}
          />
          <p className="text-xs text-warm-gray-400 -mt-2">
            Comma-separated tags for this account&apos;s niche focus
          </p>
          <Textarea
            label="Notes"
            placeholder="Optional notes about this account..."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
          />
          {error && username.trim() && (
            <p className="text-sm text-coral-600">{error}</p>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={onClose}
              disabled={createAccount.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createAccount.isPending}>
              {createAccount.isPending ? 'Adding...' : 'Add Account'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// =============================================================================
// ACCOUNT TABLE ROW
// =============================================================================

function AccountRow({
  account,
  onShowToast,
}: {
  account: RedditAccount;
  onShowToast: (message: string, variant: 'success' | 'error') => void;
}) {
  const deleteAccount = useDeleteRedditAccount();
  const [isDeleteConfirming, setIsDeleteConfirming] = useState(false);
  const deleteConfirmTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const deleteButtonRef = useRef<HTMLButtonElement>(null);

  // Reset delete confirmation after 3 seconds
  useEffect(() => {
    if (isDeleteConfirming) {
      deleteConfirmTimeoutRef.current = setTimeout(() => {
        setIsDeleteConfirming(false);
      }, 3000);
    }
    return () => {
      if (deleteConfirmTimeoutRef.current) {
        clearTimeout(deleteConfirmTimeoutRef.current);
      }
    };
  }, [isDeleteConfirming]);

  const handleDelete = useCallback(() => {
    if (!isDeleteConfirming) {
      setIsDeleteConfirming(true);
      return;
    }
    deleteAccount.mutate(account.id, {
      onSuccess: () => {
        onShowToast(`Account "${account.username}" deleted`, 'success');
      },
      onError: (err) => {
        setIsDeleteConfirming(false);
        onShowToast(err.message || 'Failed to delete account', 'error');
      },
    });
  }, [isDeleteConfirming, deleteAccount, account.id, account.username, onShowToast]);

  const handleDeleteBlur = useCallback((e: React.FocusEvent) => {
    if (!deleteButtonRef.current?.contains(e.relatedTarget as Node)) {
      setIsDeleteConfirming(false);
    }
  }, []);

  return (
    <tr className="border-b border-cream-200 hover:bg-cream-50 transition-colors">
      {/* Username */}
      <td className="px-4 py-3">
        <span className="text-sm font-medium text-warm-gray-900">
          {account.username}
        </span>
      </td>
      {/* Status */}
      <td className="px-4 py-3">
        <span
          className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm border ${getStatusBadgeClasses(account.status)}`}
        >
          {formatStatusLabel(account.status)}
        </span>
      </td>
      {/* Warmup Stage */}
      <td className="px-4 py-3 text-sm text-warm-gray-600">
        {formatWarmupLabel(account.warmup_stage)}
      </td>
      {/* Niche Tags */}
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {account.niche_tags.length > 0 ? (
            account.niche_tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center px-2 py-0.5 text-xs bg-cream-100 text-warm-gray-600 rounded-sm border border-cream-300"
              >
                {tag}
              </span>
            ))
          ) : (
            <span className="text-sm text-warm-gray-400">—</span>
          )}
        </div>
      </td>
      {/* Karma */}
      <td className="px-4 py-3 text-sm text-warm-gray-600 text-right whitespace-nowrap">
        {account.karma_post} / {account.karma_comment}
      </td>
      {/* Cooldown */}
      <td className="px-4 py-3 text-sm text-warm-gray-600 text-right whitespace-nowrap">
        {formatCooldown(account.cooldown_until)}
      </td>
      {/* Last Used */}
      <td className="px-4 py-3 text-sm text-warm-gray-600 text-right whitespace-nowrap">
        {formatRelativeTime(account.last_used_at)}
      </td>
      {/* Actions */}
      <td className="px-4 py-3 text-right">
        <Button
          ref={deleteButtonRef}
          variant={isDeleteConfirming ? 'danger' : 'ghost'}
          size="sm"
          onClick={handleDelete}
          onBlur={handleDeleteBlur}
          disabled={deleteAccount.isPending}
        >
          {deleteAccount.isPending
            ? 'Deleting...'
            : isDeleteConfirming
              ? 'Confirm?'
              : 'Delete'}
        </Button>
      </td>
    </tr>
  );
}

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function RedditAccountsPage() {
  // Filter state
  const [nicheFilter, setNicheFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [warmupFilter, setWarmupFilter] = useState('');

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Toast state
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');

  // Build query params
  const queryParams: { niche?: string; status?: string; warmup_stage?: string } = {};
  if (nicheFilter) queryParams.niche = nicheFilter;
  if (statusFilter) queryParams.status = statusFilter;
  if (warmupFilter) queryParams.warmup_stage = warmupFilter;

  const { data: accounts, isLoading } = useRedditAccounts(
    Object.keys(queryParams).length > 0 ? queryParams : undefined,
  );

  // Also fetch all accounts (no filter) for niche extraction
  const { data: allAccounts } = useRedditAccounts();
  const uniqueNiches = allAccounts ? extractUniqueNiches(allAccounts) : [];

  const handleShowToast = useCallback(
    (message: string, variant: 'success' | 'error') => {
      setToastMessage(message);
      setToastVariant(variant);
      setShowToast(true);
    },
    [],
  );

  // Loading state
  if (isLoading) {
    return <LoadingSkeleton />;
  }

  const hasFilters = !!(nicheFilter || statusFilter || warmupFilter);
  const isEmpty = !accounts || accounts.length === 0;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-warm-gray-900">
          <span className="text-warm-gray-400">Reddit</span>
          <span className="text-warm-gray-300 mx-2">&rsaquo;</span>
          <span>Accounts</span>
        </h1>
        <Button onClick={() => setIsModalOpen(true)}>+ Add Account</Button>
      </div>

      {/* Filter bar */}
      <div className="flex gap-3 mb-4">
        <FilterSelect
          label="All Niches"
          value={nicheFilter}
          options={uniqueNiches.map((n) => ({ value: n, label: n }))}
          onChange={setNicheFilter}
        />
        <FilterSelect
          label="All Stages"
          value={warmupFilter}
          options={WARMUP_STAGES}
          onChange={setWarmupFilter}
        />
        <FilterSelect
          label="All Statuses"
          value={statusFilter}
          options={ACCOUNT_STATUSES}
          onChange={setStatusFilter}
        />
        {hasFilters && (
          <button
            type="button"
            onClick={() => {
              setNicheFilter('');
              setStatusFilter('');
              setWarmupFilter('');
            }}
            className="text-sm text-lagoon-600 hover:text-lagoon-800 hover:underline px-2"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Empty state */}
      {isEmpty && !hasFilters && (
        <div className="bg-white rounded-sm border border-cream-500 shadow-sm">
          <EmptyState
            icon={
              <svg
                className="w-12 h-12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <line x1="19" y1="8" x2="19" y2="14" />
                <line x1="22" y1="11" x2="16" y2="11" />
              </svg>
            }
            title="No Reddit accounts yet"
            description="Add your first Reddit account to start managing the shared pool."
            action={
              <Button onClick={() => setIsModalOpen(true)}>
                + Add Account
              </Button>
            }
          />
        </div>
      )}

      {/* Empty filter results */}
      {isEmpty && hasFilters && (
        <div className="bg-white rounded-sm border border-cream-500 shadow-sm">
          <EmptyState
            title="No accounts match filters"
            description="Try adjusting or clearing your filters."
            action={
              <Button
                variant="secondary"
                onClick={() => {
                  setNicheFilter('');
                  setStatusFilter('');
                  setWarmupFilter('');
                }}
              >
                Clear Filters
              </Button>
            }
          />
        </div>
      )}

      {/* Table */}
      {!isEmpty && (
        <div className="bg-white rounded-sm border border-cream-500 shadow-sm overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-cream-300 bg-cream-50">
                <th className="px-4 py-2.5 text-left text-xs font-medium text-warm-gray-500 uppercase tracking-wider">
                  Username
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-warm-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-warm-gray-500 uppercase tracking-wider">
                  Warmup Stage
                </th>
                <th className="px-4 py-2.5 text-left text-xs font-medium text-warm-gray-500 uppercase tracking-wider">
                  Niche Tags
                </th>
                <th className="px-4 py-2.5 text-right text-xs font-medium text-warm-gray-500 uppercase tracking-wider">
                  Karma
                </th>
                <th className="px-4 py-2.5 text-right text-xs font-medium text-warm-gray-500 uppercase tracking-wider">
                  Cooldown
                </th>
                <th className="px-4 py-2.5 text-right text-xs font-medium text-warm-gray-500 uppercase tracking-wider">
                  Last Used
                </th>
                <th className="px-4 py-2.5 text-right text-xs font-medium text-warm-gray-500 uppercase tracking-wider">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {accounts!.map((account) => (
                <AccountRow
                  key={account.id}
                  account={account}
                  onShowToast={handleShowToast}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Account Modal */}
      <AddAccountModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />

      {/* Toast notification */}
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
