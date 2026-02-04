'use client';

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui';
import { BulletListEditor } from './BulletListEditor';
import { EditableTable, type ColumnSchema } from './EditableTable';
import { useEditorKeyboardShortcuts } from './useEditorKeyboardShortcuts';
import { type ExamplesBankData, type ProductDescriptionItem } from '../types';

interface ExamplesBankEditorProps {
  /** The examples bank data to edit */
  data: ExamplesBankData | undefined;
  /** Whether the save operation is in progress */
  isSaving?: boolean;
  /** Called when the user saves their changes */
  onSave: (data: ExamplesBankData) => void;
  /** Called when the user cancels editing */
  onCancel: () => void;
}

// Column schema for product descriptions table
const productDescriptionColumns: ColumnSchema[] = [
  { key: 'product_name', header: 'Product Name', placeholder: 'Product name...', width: 'w-1/3' },
  { key: 'description', header: 'Description', placeholder: 'Product description...', width: 'w-2/3' },
];

// Column schema for social media examples table
const socialMediaColumns: ColumnSchema[] = [
  { key: 'platform', header: 'Platform', placeholder: 'e.g., Instagram, Facebook', width: 'w-1/4' },
  { key: 'content', header: 'Post Content', placeholder: 'Social media post text...', width: 'w-3/4' },
];

// Column schema for off-brand examples table
const offBrandColumns: ColumnSchema[] = [
  { key: 'example', header: 'Off-Brand Example', placeholder: 'Example of what NOT to write...', width: 'w-2/3' },
  { key: 'reason', header: 'Why It Is Off-Brand', placeholder: 'Reason this is off-brand...', width: 'w-1/3' },
];

/**
 * Editor component for Examples Bank section.
 * Provides textareas for headlines, product descriptions, email subjects, CTAs,
 * and editable tables for social posts and off-brand examples.
 */
export function ExamplesBankEditor({
  data,
  isSaving = false,
  onSave,
  onCancel,
}: ExamplesBankEditorProps) {
  // Headlines state (array of strings, editing as bullet list)
  const [headlines, setHeadlines] = useState<string[]>(data?.headlines ?? []);

  // Product descriptions state (convert to table format)
  const [productDescriptions, setProductDescriptions] = useState<Record<string, string>[]>(
    (data?.product_descriptions ?? []).map((item) => ({
      product_name: item.product_name,
      description: item.description,
    }))
  );

  // Email subject lines state (array of strings)
  const [emailSubjects, setEmailSubjects] = useState<string[]>(data?.email_subject_lines ?? []);

  // Social media examples state (convert to table format)
  const [socialPosts, setSocialPosts] = useState<Record<string, string>[]>(
    (data?.social_media_examples ?? []).map((item) => ({
      platform: item.platform ?? '',
      content: item.content ?? '',
    }))
  );

  // CTAs state (array of strings)
  const [ctas, setCtas] = useState<string[]>(data?.ctas ?? []);

  // Off-brand examples state (convert to table format)
  const [offBrandExamples, setOffBrandExamples] = useState<Record<string, string>[]>(
    (data?.off_brand_examples ?? []).map((item) => ({
      example: item.example,
      reason: item.reason ?? '',
    }))
  );

  const handleSave = useCallback(() => {
    // Clean and convert product descriptions back to typed array
    const cleanedProductDescriptions: ProductDescriptionItem[] = productDescriptions
      .filter((row) => row.product_name?.trim() || row.description?.trim())
      .map((row) => ({
        product_name: row.product_name?.trim() || '',
        description: row.description?.trim() || '',
      }));

    // Clean and convert social media examples back to typed array
    const cleanedSocialPosts = socialPosts
      .filter((row) => row.platform?.trim() || row.content?.trim())
      .map((row) => ({
        platform: row.platform?.trim() || undefined,
        content: row.content?.trim() || undefined,
      }));

    // Clean and convert off-brand examples back to typed array
    const cleanedOffBrandExamples = offBrandExamples
      .filter((row) => row.example?.trim())
      .map((row) => ({
        example: row.example?.trim() || '',
        reason: row.reason?.trim() || undefined,
      }));

    const updatedData: ExamplesBankData = {
      headlines: headlines.length > 0 ? headlines : undefined,
      product_descriptions: cleanedProductDescriptions.length > 0 ? cleanedProductDescriptions : undefined,
      email_subject_lines: emailSubjects.length > 0 ? emailSubjects : undefined,
      social_media_examples: cleanedSocialPosts.length > 0 ? cleanedSocialPosts : undefined,
      ctas: ctas.length > 0 ? ctas : undefined,
      off_brand_examples: cleanedOffBrandExamples.length > 0 ? cleanedOffBrandExamples : undefined,
    };

    onSave(updatedData);
  }, [headlines, productDescriptions, emailSubjects, socialPosts, ctas, offBrandExamples, onSave]);

  // Use document-level keyboard shortcuts for consistent behavior
  useEditorKeyboardShortcuts({
    onSave: handleSave,
    onCancel,
    disabled: isSaving,
  });

  return (
    <div className="space-y-6">
      {/* Instructions */}
      <div className="bg-cream-50 border border-cream-300 rounded-sm p-3">
        <p className="text-sm text-warm-gray-600 mb-1">
          Build your examples bank with on-brand content samples and off-brand examples to avoid.
        </p>
        <p className="text-xs text-warm-gray-500">
          Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">⌘S</kbd> to save or{' '}
          <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel.
        </p>
      </div>

      {/* Headlines That Work */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Headlines That Work
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Strong, on-brand headlines that can be used as templates or inspiration.
        </p>
        <BulletListEditor
          value={headlines}
          onChange={setHeadlines}
          placeholder="Add a headline example..."
          addButtonText="Add headline"
          disabled={isSaving}
        />
      </section>

      {/* Product Descriptions */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Product Description Examples
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Sample product descriptions showing the ideal format and tone.
        </p>
        <EditableTable
          value={productDescriptions}
          onChange={setProductDescriptions}
          columns={productDescriptionColumns}
          addButtonText="Add product description"
          disabled={isSaving}
        />
      </section>

      {/* Email Subject Lines */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Email Subject Lines
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Effective email subject lines that drive opens.
        </p>
        <BulletListEditor
          value={emailSubjects}
          onChange={setEmailSubjects}
          placeholder="Add an email subject line..."
          addButtonText="Add subject line"
          disabled={isSaving}
        />
      </section>

      {/* Social Media Posts */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Social Media Posts
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Example posts for different platforms (Instagram, Facebook, etc.).
        </p>
        <EditableTable
          value={socialPosts}
          onChange={setSocialPosts}
          columns={socialMediaColumns}
          addButtonText="Add social post"
          disabled={isSaving}
        />
      </section>

      {/* CTAs That Work */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          CTAs That Work
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Effective calls-to-action that drive conversions.
        </p>
        <BulletListEditor
          value={ctas}
          onChange={setCtas}
          placeholder="Add a CTA..."
          addButtonText="Add CTA"
          disabled={isSaving}
        />
      </section>

      {/* Off-Brand Examples */}
      <section className="bg-coral-50 border border-coral-200 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-coral-800 mb-3 uppercase tracking-wide">
          What NOT to Write (Off-Brand)
        </h3>
        <p className="text-xs text-coral-600 mb-3">
          Examples of content that should be avoided and why.
        </p>
        <EditableTable
          value={offBrandExamples}
          onChange={setOffBrandExamples}
          columns={offBrandColumns}
          addButtonText="Add off-brand example"
          disabled={isSaving}
        />
      </section>

      {/* Action buttons */}
      <div className="flex justify-end gap-3 pt-4 border-t border-cream-200">
        <Button variant="secondary" onClick={onCancel} disabled={isSaving}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>
    </div>
  );
}

export type { ExamplesBankEditorProps };
