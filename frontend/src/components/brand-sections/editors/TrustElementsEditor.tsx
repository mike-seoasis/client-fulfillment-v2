'use client';

import { useState, useCallback } from 'react';
import { Button, Input, Textarea } from '@/components/ui';
import { BulletListEditor } from './BulletListEditor';
import { EditableTable, type ColumnSchema } from './EditableTable';
import { useEditorKeyboardShortcuts } from './useEditorKeyboardShortcuts';
import { type TrustElementsData, type CustomerQuote } from '../types';

interface TrustElementsEditorProps {
  /** The trust elements data to edit */
  data: TrustElementsData | undefined;
  /** Whether the save operation is in progress */
  isSaving?: boolean;
  /** Called when the user saves their changes */
  onSave: (data: TrustElementsData) => void;
  /** Called when the user cancels editing */
  onCancel: () => void;
}

// Column schema for customer quotes table
const customerQuoteColumns: ColumnSchema[] = [
  { key: 'quote', header: 'Quote', placeholder: 'Customer testimonial text...', width: 'w-2/3' },
  { key: 'attribution', header: 'Attribution', placeholder: 'Customer name / title', width: 'w-1/3' },
];

/**
 * Editor component for Trust Elements section.
 * Provides inputs for hard numbers, bullet list editors for credentials/guarantees,
 * and editable table for customer quotes.
 */
export function TrustElementsEditor({
  data,
  isSaving = false,
  onSave,
  onCancel,
}: TrustElementsEditorProps) {
  // Defensive helper to ensure array
  const toArray = <T,>(val: T[] | undefined | null): T[] => (Array.isArray(val) ? val : []);

  // Hard numbers state
  const [customerCount, setCustomerCount] = useState(data?.hard_numbers?.customer_count ?? '');
  const [yearsInBusiness, setYearsInBusiness] = useState(data?.hard_numbers?.years_in_business ?? '');
  const [productsSold, setProductsSold] = useState(data?.hard_numbers?.products_sold ?? '');
  const [averageRating, setAverageRating] = useState(data?.hard_numbers?.average_store_rating ?? '');
  const [reviewCount, setReviewCount] = useState(data?.hard_numbers?.review_count ?? '');

  // Credentials and endorsements state
  const [credentials, setCredentials] = useState<string[]>(toArray(data?.credentials));
  const [mediaPress, setMediaPress] = useState<string[]>(toArray(data?.media_press));
  const [endorsements, setEndorsements] = useState<string[]>(toArray(data?.endorsements));

  // Guarantees state
  const [returnPolicy, setReturnPolicy] = useState(data?.guarantees?.return_policy ?? '');
  const [warranty, setWarranty] = useState(data?.guarantees?.warranty ?? '');
  const [satisfactionGuarantee, setSatisfactionGuarantee] = useState(
    data?.guarantees?.satisfaction_guarantee ?? ''
  );

  // Customer quotes state (convert to table format)
  const [customerQuotes, setCustomerQuotes] = useState<Record<string, string>[]>(
    toArray(data?.customer_quotes).map((q) => ({
      quote: q.quote,
      attribution: q.attribution,
    }))
  );

  const handleSave = useCallback(() => {
    // Build hard_numbers object only if at least one field has a value
    const hardNumbersData = {
      customer_count: customerCount.trim() || undefined,
      years_in_business: yearsInBusiness.trim() || undefined,
      products_sold: productsSold.trim() || undefined,
      average_store_rating: averageRating.trim() || undefined,
      review_count: reviewCount.trim() || undefined,
    };
    const hasHardNumbers = Object.values(hardNumbersData).some((v) => v);

    // Build guarantees object only if at least one field has a value
    const guaranteesData = {
      return_policy: returnPolicy.trim() || undefined,
      warranty: warranty.trim() || undefined,
      satisfaction_guarantee: satisfactionGuarantee.trim() || undefined,
    };
    const hasGuarantees = Object.values(guaranteesData).some((v) => v);

    // Convert customer quotes table data back to typed array, filtering empty rows
    const cleanedQuotes: CustomerQuote[] = customerQuotes
      .filter((row) => row.quote?.trim() || row.attribution?.trim())
      .map((row) => ({
        quote: row.quote?.trim() || '',
        attribution: row.attribution?.trim() || '',
      }));

    const updatedData: TrustElementsData = {
      hard_numbers: hasHardNumbers ? hardNumbersData : undefined,
      credentials: credentials.length > 0 ? credentials : undefined,
      media_press: mediaPress.length > 0 ? mediaPress : undefined,
      endorsements: endorsements.length > 0 ? endorsements : undefined,
      guarantees: hasGuarantees ? guaranteesData : undefined,
      customer_quotes: cleanedQuotes.length > 0 ? cleanedQuotes : undefined,
    };

    onSave(updatedData);
  }, [
    customerCount,
    yearsInBusiness,
    productsSold,
    averageRating,
    reviewCount,
    credentials,
    mediaPress,
    endorsements,
    returnPolicy,
    warranty,
    satisfactionGuarantee,
    customerQuotes,
    onSave,
  ]);

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
          Document your trust signals and proof points. These build credibility with potential customers.
        </p>
        <p className="text-xs text-warm-gray-500">
          Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">⌘S</kbd> to save or{' '}
          <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel.
        </p>
      </div>

      {/* Hard Numbers */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Hard Numbers
        </h3>
        <p className="text-xs text-warm-gray-500 mb-4">
          Specific, quantifiable achievements that demonstrate your track record.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-warm-gray-600 mb-1">
              Customer Count
            </label>
            <Input
              value={customerCount}
              onChange={(e) => setCustomerCount(e.target.value)}
              placeholder="e.g., 50,000+ happy customers"
              disabled={isSaving}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-gray-600 mb-1">
              Years in Business
            </label>
            <Input
              value={yearsInBusiness}
              onChange={(e) => setYearsInBusiness(e.target.value)}
              placeholder="e.g., Since 2015"
              disabled={isSaving}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-gray-600 mb-1">
              Products Sold
            </label>
            <Input
              value={productsSold}
              onChange={(e) => setProductsSold(e.target.value)}
              placeholder="e.g., 1 million+ units shipped"
              disabled={isSaving}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-gray-600 mb-1">
              Average Rating
            </label>
            <Input
              value={averageRating}
              onChange={(e) => setAverageRating(e.target.value)}
              placeholder="e.g., 4.8 out of 5 stars"
              disabled={isSaving}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-gray-600 mb-1">
              Review Count
            </label>
            <Input
              value={reviewCount}
              onChange={(e) => setReviewCount(e.target.value)}
              placeholder="e.g., 10,000+ reviews"
              disabled={isSaving}
            />
          </div>
        </div>
      </section>

      {/* Credentials */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Credentials & Certifications
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Official certifications, awards, or industry recognitions.
        </p>
        <BulletListEditor
          value={credentials}
          onChange={setCredentials}
          placeholder="Add a credential or certification..."
          addButtonText="Add credential"
          disabled={isSaving}
        />
      </section>

      {/* Media & Press */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Media & Press
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Notable media mentions, press coverage, or features.
        </p>
        <BulletListEditor
          value={mediaPress}
          onChange={setMediaPress}
          placeholder="Add a media mention or press feature..."
          addButtonText="Add media mention"
          disabled={isSaving}
        />
      </section>

      {/* Endorsements */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Endorsements
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Celebrity endorsements, influencer partnerships, or notable supporters.
        </p>
        <BulletListEditor
          value={endorsements}
          onChange={setEndorsements}
          placeholder="Add an endorsement..."
          addButtonText="Add endorsement"
          disabled={isSaving}
        />
      </section>

      {/* Guarantees */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Guarantees & Policies
        </h3>
        <p className="text-xs text-warm-gray-500 mb-4">
          Customer-friendly policies that reduce purchase risk.
        </p>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-warm-gray-600 mb-1">
              Return Policy
            </label>
            <Textarea
              value={returnPolicy}
              onChange={(e) => setReturnPolicy(e.target.value)}
              placeholder="e.g., 30-day no-questions-asked returns"
              disabled={isSaving}
              rows={2}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-gray-600 mb-1">
              Warranty
            </label>
            <Textarea
              value={warranty}
              onChange={(e) => setWarranty(e.target.value)}
              placeholder="e.g., Lifetime warranty on all products"
              disabled={isSaving}
              rows={2}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-warm-gray-600 mb-1">
              Satisfaction Guarantee
            </label>
            <Textarea
              value={satisfactionGuarantee}
              onChange={(e) => setSatisfactionGuarantee(e.target.value)}
              placeholder="e.g., 100% satisfaction guaranteed or your money back"
              disabled={isSaving}
              rows={2}
            />
          </div>
        </div>
      </section>

      {/* Customer Quotes */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Customer Quotes (Approved for Use)
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Testimonials and quotes from real customers that can be used in marketing.
        </p>
        <EditableTable
          value={customerQuotes}
          onChange={setCustomerQuotes}
          columns={customerQuoteColumns}
          addButtonText="Add quote"
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

export type { TrustElementsEditorProps };
