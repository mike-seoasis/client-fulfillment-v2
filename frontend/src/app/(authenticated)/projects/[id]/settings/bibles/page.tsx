'use client';

import { useState, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useBibles, useImportBible } from '@/hooks/useBibles';
import { Button, ButtonLink, Toast } from '@/components/ui';

function toRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return 'Unknown';
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function BibleStatusBadge({ isActive }: { isActive: boolean }) {
  if (isActive) {
    return (
      <span className="inline-flex items-center gap-1 text-xs bg-palm-50 text-palm-700 px-2 py-0.5 rounded-sm border border-palm-200">
        Active
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-cream-100 text-warm-gray-600 px-2 py-0.5 rounded-sm border border-cream-300">
      Draft
    </span>
  );
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse space-y-3">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="bg-white rounded-sm border border-cream-500 p-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <div className="h-4 bg-cream-300 rounded-sm w-48 mb-2" />
              <div className="h-3 bg-cream-300 rounded-sm w-24" />
            </div>
            <div className="h-5 bg-cream-300 rounded-sm w-16" />
          </div>
        </div>
      ))}
    </div>
  );
}

function ErrorState() {
  return (
    <div className="bg-white rounded-sm border border-cream-500 p-12 text-center shadow-sm">
      <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-coral-50 mb-4">
        <svg
          className="w-6 h-6 text-coral-500"
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
      <h3 className="text-lg font-medium text-warm-gray-900 mb-1">
        Failed to load bibles
      </h3>
      <p className="text-warm-gray-600 text-sm">
        Something went wrong. Try refreshing the page.
      </p>
    </div>
  );
}

const MAX_IMPORT_SIZE = 500_000; // 500 KB

export default function BiblesListPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');

  const { data: bibles, isLoading, error } = useBibles(projectId);
  const { mutateAsync: runImport, isPending: isImporting } = useImportBible();

  const handleImport = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      if (file.size > MAX_IMPORT_SIZE) {
        setToastMessage('File too large — max 500 KB');
        setToastVariant('error');
        setShowToast(true);
        if (fileInputRef.current) fileInputRef.current.value = '';
        return;
      }

      try {
        const markdown = await file.text();
        const result = await runImport({ projectId, markdown });
        router.push(
          `/projects/${projectId}/settings/bibles/${result.id}`
        );
      } catch {
        setToastMessage('Failed to import bible');
        setToastVariant('error');
        setShowToast(true);
      }

      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    },
    [projectId, runImport, router]
  );

  return (
    <div>
      {/* Back link */}
      <Link
        href={`/projects/${projectId}`}
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
        Back to Project
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-warm-gray-900 mb-1">
            Knowledge Bibles
          </h1>
          <p className="text-warm-gray-600 text-sm">
            Domain expertise documents injected into content generation prompts
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => fileInputRef.current?.click()}
            disabled={isImporting}
          >
            {isImporting ? 'Importing...' : 'Import'}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".md,.markdown,.txt"
            className="hidden"
            onChange={handleImport}
          />
          <ButtonLink href={`/projects/${projectId}/settings/bibles/new`}>
            + New Bible
          </ButtonLink>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <LoadingSkeleton />
      ) : error ? (
        <ErrorState />
      ) : !bibles || bibles.length === 0 ? (
        <div className="bg-white rounded-sm border border-cream-500 p-12 text-center shadow-sm">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-palm-50 mb-4">
            <svg
              className="w-6 h-6 text-palm-500"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-warm-gray-900 mb-1">
            No knowledge bibles yet
          </h3>
          <p className="text-warm-gray-600 text-sm mb-4">
            Create a bible to inject domain expertise into content generation
          </p>
          <ButtonLink href={`/projects/${projectId}/settings/bibles/new`}>
            + New Bible
          </ButtonLink>
        </div>
      ) : (
        <div className="bg-white rounded-sm border border-cream-500 shadow-sm overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-cream-300 bg-cream-50">
                <th className="text-left text-xs font-medium text-warm-gray-600 uppercase tracking-wide px-4 py-3">
                  Name
                </th>
                <th className="text-left text-xs font-medium text-warm-gray-600 uppercase tracking-wide px-4 py-3">
                  Keywords
                </th>
                <th className="text-left text-xs font-medium text-warm-gray-600 uppercase tracking-wide px-4 py-3">
                  Updated
                </th>
                <th className="text-left text-xs font-medium text-warm-gray-600 uppercase tracking-wide px-4 py-3">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {bibles.map((bible) => (
                <tr
                  key={bible.id}
                  tabIndex={0}
                  role="link"
                  className="border-b border-cream-200 last:border-b-0 hover:bg-cream-50 cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-palm-200"
                  onClick={() =>
                    router.push(
                      `/projects/${projectId}/settings/bibles/${bible.id}`
                    )
                  }
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      router.push(
                        `/projects/${projectId}/settings/bibles/${bible.id}`
                      );
                    }
                  }}
                >
                  <td className="px-4 py-3">
                    <span className="font-medium text-warm-gray-900">
                      {bible.name}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-warm-gray-600">
                    {bible.trigger_keywords.length}
                  </td>
                  <td className="px-4 py-3 text-sm text-warm-gray-500">
                    {toRelativeTime(bible.updated_at)}
                  </td>
                  <td className="px-4 py-3">
                    <BibleStatusBadge isActive={bible.is_active} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Generate from Transcript */}
      <div className="mt-6 bg-cream-50 rounded-sm border border-cream-300 border-dashed p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium text-warm-gray-700 mb-1">
              Generate from Transcript
            </h3>
            <p className="text-xs text-warm-gray-500">
              Automatically create a bible from a client interview transcript
            </p>
          </div>
          <ButtonLink href={`/projects/${projectId}/settings/bibles/generate`} variant="secondary">
            Generate from Transcript
          </ButtonLink>
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
