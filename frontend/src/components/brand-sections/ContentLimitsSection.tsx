'use client';

import { EmptySection } from './SectionCard';
import { type ContentLimitsData, type BaseSectionProps } from './types';

interface ContentLimitsSectionProps extends BaseSectionProps {
  data?: ContentLimitsData;
}

export function ContentLimitsSection({ data }: ContentLimitsSectionProps) {
  if (!data) {
    return <EmptySection message="No content limits configured. Using global defaults." />;
  }

  const collectionLimit = data.collection_max_words ?? data.max_word_count ?? null;
  const blogLimit = data.blog_max_words ?? null;

  if (collectionLimit === null && blogLimit === null) {
    return <EmptySection message="No content limits configured. Using global defaults." />;
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-cream-50 border border-cream-300 rounded-sm p-4">
          <h3 className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider mb-2">
            Collection Page Max Words
          </h3>
          <p className="text-lg font-semibold text-warm-gray-900">
            {collectionLimit != null ? `${collectionLimit.toLocaleString()} words` : 'Using global default'}
          </p>
          <p className="text-xs text-warm-gray-500 mt-1">
            Applies to bottom_description field
          </p>
        </div>
        <div className="bg-cream-50 border border-cream-300 rounded-sm p-4">
          <h3 className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider mb-2">
            Blog Post Max Words
          </h3>
          <p className="text-lg font-semibold text-warm-gray-900">
            {blogLimit != null ? `${blogLimit.toLocaleString()} words` : 'Using global default'}
          </p>
          <p className="text-xs text-warm-gray-500 mt-1">
            Applies to blog content field
          </p>
        </div>
      </div>
    </div>
  );
}
