'use client';

import { useCallback, useState, type ChangeEvent } from 'react';

export interface ParsedUrl {
  url: string;
  isValid: boolean;
}

interface UrlUploaderProps {
  value?: string;
  onChange?: (urls: ParsedUrl[]) => void;
  onRawChange?: (rawText: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

/**
 * Validate that a string is a valid URL with http/https protocol
 */
function isValidUrl(str: string): boolean {
  try {
    const url = new URL(str);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

/**
 * Parse raw text input into an array of URLs
 * - Splits by newline
 * - Trims whitespace
 * - Filters out empty lines
 * - Validates URL format
 */
function parseUrls(rawText: string): ParsedUrl[] {
  if (!rawText.trim()) {
    return [];
  }

  return rawText
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => ({
      url: line,
      isValid: isValidUrl(line),
    }));
}

function UrlUploader({
  value = '',
  onChange,
  onRawChange,
  placeholder = 'https://example.com/collections/summer-collection\nhttps://example.com/collections/winter-collection',
  disabled = false,
  className = '',
}: UrlUploaderProps) {
  const [rawText, setRawText] = useState(value);

  const handleChange = useCallback(
    (e: ChangeEvent<HTMLTextAreaElement>) => {
      const newText = e.target.value;
      setRawText(newText);

      // Notify parent of raw text change
      if (onRawChange) {
        onRawChange(newText);
      }

      // Parse and notify parent of parsed URLs
      if (onChange) {
        const parsed = parseUrls(newText);
        onChange(parsed);
      }
    },
    [onChange, onRawChange]
  );

  const handleBlur = useCallback(() => {
    // Re-parse on blur to ensure state is synced
    if (onChange) {
      const parsed = parseUrls(rawText);
      onChange(parsed);
    }
  }, [onChange, rawText]);

  const baseClasses =
    'block w-full px-4 py-3 text-warm-gray-900 bg-white border border-cream-400 rounded-sm transition-colors duration-150 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-palm-400 focus:border-transparent disabled:bg-cream-100 disabled:cursor-not-allowed resize-none font-mono text-sm';

  const hoverClasses = disabled ? '' : 'hover:border-cream-500';

  return (
    <div className={`w-full ${className}`}>
      <textarea
        value={rawText}
        onChange={handleChange}
        onBlur={handleBlur}
        placeholder={placeholder}
        disabled={disabled}
        rows={8}
        className={`${baseClasses} ${hoverClasses} min-h-[200px]`}
        aria-label="URLs to crawl, one per line"
      />
      <p className="mt-2 text-sm text-warm-gray-500">
        Enter one URL per line. URLs should start with https:// or http://
      </p>
    </div>
  );
}

export { UrlUploader, type UrlUploaderProps, parseUrls, isValidUrl };
