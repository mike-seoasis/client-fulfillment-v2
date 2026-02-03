'use client';

import { type ReactNode } from 'react';

interface SectionCardProps {
  title: string;
  children: ReactNode;
  className?: string;
}

/**
 * A styled card for displaying content within a section.
 * Uses the tropical oasis design system.
 */
export function SectionCard({ title, children, className = '' }: SectionCardProps) {
  return (
    <div className={`mb-6 ${className}`}>
      <h3 className="text-sm font-semibold text-warm-gray-700 mb-3">{title}</h3>
      <div className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        {children}
      </div>
    </div>
  );
}

interface InfoRowProps {
  label: string;
  value?: string | null;
}

/**
 * A label-value pair for displaying structured data.
 */
export function InfoRow({ label, value }: InfoRowProps) {
  if (!value) return null;

  return (
    <div className="flex items-start py-1.5 border-b border-cream-200 last:border-b-0">
      <span className="text-warm-gray-500 text-sm min-w-[140px] flex-shrink-0">{label}:</span>
      <span className="text-warm-gray-800 text-sm">{value}</span>
    </div>
  );
}

interface BulletListProps {
  items?: string[];
  emptyMessage?: string;
}

/**
 * A styled bullet list for arrays of strings.
 */
export function BulletList({ items, emptyMessage = 'None specified' }: BulletListProps) {
  if (!items || items.length === 0) {
    return <span className="text-warm-gray-400 text-sm italic">{emptyMessage}</span>;
  }

  return (
    <ul className="space-y-1.5">
      {items.map((item, index) => (
        <li key={index} className="flex items-start text-sm text-warm-gray-700">
          <span className="text-palm-500 mr-2 flex-shrink-0">•</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

interface TagListProps {
  items?: string[];
  emptyMessage?: string;
  variant?: 'default' | 'success' | 'danger';
}

/**
 * A horizontal list of tags/chips.
 */
export function TagList({ items, emptyMessage = 'None specified', variant = 'default' }: TagListProps) {
  if (!items || items.length === 0) {
    return <span className="text-warm-gray-400 text-sm italic">{emptyMessage}</span>;
  }

  const variantStyles = {
    default: 'bg-cream-100 text-warm-gray-700 border-cream-300',
    success: 'bg-palm-50 text-palm-700 border-palm-200',
    danger: 'bg-coral-50 text-coral-700 border-coral-200',
  };

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item, index) => (
        <span
          key={index}
          className={`inline-flex items-center px-2.5 py-1 text-sm border rounded-sm ${variantStyles[variant]}`}
        >
          {item}
        </span>
      ))}
    </div>
  );
}

interface EmptySectionProps {
  message?: string;
}

/**
 * Placeholder for empty section content.
 */
export function EmptySection({ message = 'No data available' }: EmptySectionProps) {
  return (
    <div className="flex items-center justify-center py-8">
      <p className="text-warm-gray-400 text-sm italic">{message}</p>
    </div>
  );
}
