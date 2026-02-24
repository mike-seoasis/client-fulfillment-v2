'use client';

import { useCallback, useState, type ChangeEvent } from 'react';

export interface ParsedUrl {
  url: string;
  normalizedUrl: string;
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
 * Extract the domain (hostname) from a URL string
 * Returns lowercase hostname, or null if URL is invalid
 */
function getDomain(urlStr: string): string | null {
  try {
    const url = new URL(urlStr);
    return url.hostname.toLowerCase();
  } catch {
    return null;
  }
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
 * Normalize a URL:
 * - Lowercase the domain (hostname)
 * - Remove trailing slash except for root paths
 * - Preserve original path case (paths can be case-sensitive)
 */
function normalizeUrl(urlStr: string): string {
  try {
    const url = new URL(urlStr);
    // Reconstruct URL with lowercase hostname
    let normalized = `${url.protocol}//${url.hostname.toLowerCase()}`;

    // Add port if present and non-standard
    if (url.port) {
      normalized += `:${url.port}`;
    }

    // Add pathname (preserve original case)
    let path = url.pathname;

    // Remove trailing slash unless it's the root path
    if (path.length > 1 && path.endsWith('/')) {
      path = path.slice(0, -1);
    }

    normalized += path;

    // Add search params and hash if present
    normalized += url.search;
    normalized += url.hash;

    return normalized;
  } catch {
    // If URL parsing fails, return the original string trimmed
    return urlStr.trim();
  }
}

/**
 * Parse raw text input into an array of URLs
 * - Splits by newline
 * - Trims whitespace
 * - Filters out empty lines
 * - Validates URL format
 * - Normalizes URLs (lowercase domain, consistent trailing slash)
 * - Deduplicates by normalized URL
 */
function parseUrls(rawText: string): ParsedUrl[] {
  if (!rawText.trim()) {
    return [];
  }

  const seen = new Set<string>();
  const results: ParsedUrl[] = [];

  const lines = rawText
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  for (const line of lines) {
    const valid = isValidUrl(line);
    const normalized = valid ? normalizeUrl(line) : line.toLowerCase();

    // Deduplicate by normalized URL
    if (!seen.has(normalized)) {
      seen.add(normalized);
      results.push({
        url: line,
        normalizedUrl: normalized,
        isValid: valid,
      });
    }
  }

  return results;
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

export { UrlUploader, type UrlUploaderProps, parseUrls, isValidUrl, normalizeUrl, getDomain };
