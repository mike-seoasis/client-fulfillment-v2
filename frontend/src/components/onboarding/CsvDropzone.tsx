'use client';

import { useCallback, useState, useRef, type DragEvent } from 'react';
import * as Papa from 'papaparse';

export interface CsvParseResult {
  urls: string[];
  error: string | null;
  filename: string | null;
}

interface CsvDropzoneProps {
  onParsed: (result: CsvParseResult) => void;
  disabled?: boolean;
  className?: string;
}

/**
 * Extract URLs from parsed CSV data
 * - Looks for 'url' column (case-insensitive) first
 * - Falls back to first column if no 'url' column found
 * - Filters empty values
 */
function extractUrlsFromCsv(data: Record<string, string>[], fields: string[] | undefined): string[] {
  if (!data || data.length === 0) {
    return [];
  }

  // Find 'url' column (case-insensitive)
  const urlColumnName = fields?.find(
    (field) => field.toLowerCase() === 'url'
  );

  // Use 'url' column or fall back to first column
  const columnToUse = urlColumnName || (fields && fields.length > 0 ? fields[0] : null);

  if (!columnToUse) {
    return [];
  }

  return data
    .map((row) => row[columnToUse]?.trim())
    .filter((url): url is string => !!url && url.length > 0);
}

function UploadIcon({ className }: { className?: string }) {
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
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}

function FileIcon({ className }: { className?: string }) {
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
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  );
}

function CsvDropzone({
  onParsed,
  disabled = false,
  className = '',
}: CsvDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [loadedFile, setLoadedFile] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const parseFile = useCallback(
    (file: File) => {
      // Validate file type
      const validTypes = ['text/csv', 'application/vnd.ms-excel', '.csv'];
      const isValidType =
        validTypes.includes(file.type) ||
        file.name.toLowerCase().endsWith('.csv');

      if (!isValidType) {
        onParsed({
          urls: [],
          error: 'Invalid file type. Please upload a CSV file.',
          filename: file.name,
        });
        setLoadedFile(null);
        return;
      }

      Papa.parse<Record<string, string>>(file, {
        header: true,
        skipEmptyLines: true,
        complete: (results) => {
          const urls = extractUrlsFromCsv(results.data, results.meta.fields);

          if (urls.length === 0) {
            onParsed({
              urls: [],
              error:
                'No URLs found in CSV. Make sure the file has a "url" column or URLs in the first column.',
              filename: file.name,
            });
            setLoadedFile(null);
          } else {
            onParsed({
              urls,
              error: null,
              filename: file.name,
            });
            setLoadedFile(file.name);
          }
        },
        error: (error) => {
          onParsed({
            urls: [],
            error: `Failed to parse CSV: ${error.message}`,
            filename: file.name,
          });
          setLoadedFile(null);
        },
      });
    },
    [onParsed]
  );

  const handleDragOver = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      if (!disabled) {
        setIsDragging(true);
      }
    },
    [disabled]
  );

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      if (disabled) return;

      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        parseFile(files[0]);
      }
    },
    [disabled, parseFile]
  );

  const handleClick = useCallback(() => {
    if (!disabled && fileInputRef.current) {
      fileInputRef.current.click();
    }
  }, [disabled]);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        parseFile(files[0]);
      }
      // Reset input so the same file can be selected again
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    },
    [parseFile]
  );

  const handleClear = useCallback(() => {
    setLoadedFile(null);
    onParsed({
      urls: [],
      error: null,
      filename: null,
    });
  }, [onParsed]);

  const baseClasses =
    'relative border-2 border-dashed rounded-sm p-6 text-center transition-colors duration-150';
  const stateClasses = isDragging
    ? 'border-palm-400 bg-palm-50'
    : loadedFile
    ? 'border-palm-300 bg-palm-50'
    : 'border-cream-400 bg-cream-50 hover:border-cream-500';
  const cursorClasses = disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer';

  return (
    <div className={className}>
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        className={`${baseClasses} ${stateClasses} ${cursorClasses}`}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label="Upload CSV file"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleClick();
          }
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv,application/vnd.ms-excel"
          onChange={handleFileChange}
          className="hidden"
          disabled={disabled}
          aria-hidden="true"
        />

        {loadedFile ? (
          <div className="flex flex-col items-center">
            <FileIcon className="w-8 h-8 text-palm-500 mb-2" />
            <p className="text-sm font-medium text-warm-gray-700">{loadedFile}</p>
            <p className="text-xs text-warm-gray-500 mt-1">CSV loaded successfully</p>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleClear();
              }}
              className="mt-2 text-xs text-coral-600 hover:text-coral-700 underline"
            >
              Remove file
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center">
            <UploadIcon className="w-8 h-8 text-warm-gray-400 mb-2" />
            <p className="text-sm text-warm-gray-600">
              <span className="font-medium text-palm-600">Click to upload</span> or
              drag and drop
            </p>
            <p className="text-xs text-warm-gray-400 mt-1">CSV files only</p>
          </div>
        )}
      </div>
    </div>
  );
}

export { CsvDropzone, type CsvDropzoneProps, extractUrlsFromCsv };
