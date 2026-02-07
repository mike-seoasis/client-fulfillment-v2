'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import { usePageContent } from '@/hooks/useContentGeneration';
import { Button } from '@/components/ui';

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

function FieldCard({
  label,
  value,
  html,
  mono,
}: {
  label: string;
  value: string | null;
  html?: boolean;
  mono?: boolean;
}) {
  if (!value) return null;

  return (
    <div className="border border-cream-400 rounded-sm overflow-hidden">
      <div className="px-3 py-2 bg-cream-100 border-b border-cream-400">
        <span className="text-xs font-medium text-warm-gray-700 uppercase tracking-wide">
          {label}
        </span>
      </div>
      <div className="px-4 py-3">
        {html ? (
          <div
            className="prose prose-sm max-w-none text-warm-gray-800"
            dangerouslySetInnerHTML={{ __html: value }}
          />
        ) : (
          <p className={`text-sm text-warm-gray-800 leading-relaxed ${mono ? 'font-mono' : ''}`}>
            {value}
          </p>
        )}
      </div>
    </div>
  );
}

export default function PageContentViewPage() {
  const params = useParams();
  const projectId = params.id as string;
  const pageId = params.pageId as string;

  const { data: project } = useProject(projectId);
  const { data: content, isLoading, isError } = usePageContent(projectId, pageId);

  return (
    <div>
      {/* Breadcrumb */}
      <nav className="flex items-center text-sm text-warm-gray-600 mb-6">
        <Link
          href={`/projects/${projectId}/onboarding/content`}
          className="hover:text-warm-gray-900 flex items-center"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          {project?.name ?? 'Project'}
        </Link>
        <span className="mx-2">&rsaquo;</span>
        <span className="text-warm-gray-900">Content Preview</span>
      </nav>

      {/* Loading */}
      {isLoading && (
        <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm animate-pulse">
          <div className="h-6 bg-cream-300 rounded w-64 mb-4" />
          <div className="space-y-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-cream-200 rounded" />
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm text-center py-12">
          <p className="text-warm-gray-600 mb-4">Failed to load content for this page.</p>
          <Link href={`/projects/${projectId}/onboarding/content`}>
            <Button variant="secondary">Back to Content</Button>
          </Link>
        </div>
      )}

      {/* Content */}
      {content && (
        <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-warm-gray-900">Content Preview</h2>
            {content.word_count && (
              <span className="text-xs text-warm-gray-500 font-mono">
                {content.word_count.toLocaleString()} words
              </span>
            )}
          </div>

          <div className="space-y-4">
            <FieldCard label="Page Title" value={content.page_title} />
            <FieldCard label="Meta Description" value={content.meta_description} />
            <FieldCard label="Top Description" value={content.top_description} />
            <FieldCard label="Bottom Description (HTML)" value={content.bottom_description} html />
          </div>

          {/* QA Results */}
          {content.qa_results && Object.keys(content.qa_results).length > 0 && (
            <div className="mt-6 border border-cream-400 rounded-sm overflow-hidden">
              <div className="px-3 py-2 bg-cream-100 border-b border-cream-400">
                <span className="text-xs font-medium text-warm-gray-700 uppercase tracking-wide">
                  QA Results
                </span>
              </div>
              <div className="px-4 py-3">
                <pre className="text-xs text-warm-gray-700 font-mono whitespace-pre-wrap">
                  {JSON.stringify(content.qa_results, null, 2)}
                </pre>
              </div>
            </div>
          )}

          <hr className="border-cream-500 my-6" />

          <div className="flex justify-end">
            <Link href={`/projects/${projectId}/onboarding/content`}>
              <Button variant="secondary">Back to Content</Button>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
