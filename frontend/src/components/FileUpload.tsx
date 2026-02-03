'use client';

import { useCallback, useRef, useState, type DragEvent, type ChangeEvent } from 'react';
import { Button } from './ui/Button';

// Validation constants
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10MB
const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt'];
const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
];

interface FileWithError {
  file: File;
  error?: string;
}

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  progress: number; // 0-100
  status: 'pending' | 'uploading' | 'complete' | 'error';
  error?: string;
}

interface FileUploadProps {
  onFilesSelected?: (files: File[]) => void;
  onFileRemove?: (fileId: string) => void;
  uploadedFiles?: UploadedFile[];
  disabled?: boolean;
  className?: string;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function validateFile(file: File): string | undefined {
  // Check file size
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return `File exceeds maximum size of ${formatFileSize(MAX_FILE_SIZE_BYTES)}`;
  }

  // Check file type by MIME type
  const normalizedType = file.type.split(';')[0].trim();
  if (ALLOWED_MIME_TYPES.includes(normalizedType)) {
    return undefined;
  }

  // Fallback: check by extension
  const ext = '.' + file.name.split('.').pop()?.toLowerCase();
  if (ALLOWED_EXTENSIONS.includes(ext)) {
    return undefined;
  }

  return `Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`;
}

function FileUpload({
  onFilesSelected,
  onFileRemove,
  uploadedFiles = [],
  disabled = false,
  className = '',
}: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [validationErrors, setValidationErrors] = useState<FileWithError[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounter = useRef(0);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;

      const validFiles: File[] = [];
      const errors: FileWithError[] = [];

      Array.from(files).forEach((file) => {
        const error = validateFile(file);
        if (error) {
          errors.push({ file, error });
        } else {
          validFiles.push(file);
        }
      });

      setValidationErrors(errors);

      if (validFiles.length > 0 && onFilesSelected) {
        onFilesSelected(validFiles);
      }
    },
    [onFilesSelected]
  );

  const handleDragEnter = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  }, []);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current === 0) {
      setIsDragging(false);
    }
  }, []);

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      dragCounter.current = 0;

      if (disabled) return;

      handleFiles(e.dataTransfer.files);
    },
    [disabled, handleFiles]
  );

  const handleInputChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      handleFiles(e.target.files);
      // Reset input so the same file can be selected again
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    },
    [handleFiles]
  );

  const handleBrowseClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleRemoveError = useCallback((index: number) => {
    setValidationErrors((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const dropzoneClasses = isDragging
    ? 'border-palm-400 bg-palm-50'
    : 'border-cream-400 hover:border-cream-500 bg-white';

  const disabledClasses = disabled ? 'opacity-50 cursor-not-allowed' : '';

  return (
    <div className={`w-full ${className}`}>
      {/* Drop zone */}
      <div
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-sm p-8 text-center transition-colors duration-150 ${dropzoneClasses} ${disabledClasses}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ALLOWED_EXTENSIONS.join(',')}
          onChange={handleInputChange}
          disabled={disabled}
          className="hidden"
          aria-label="File upload input"
        />

        <div className="flex flex-col items-center gap-3">
          {/* Upload icon */}
          <div className="w-12 h-12 rounded-full bg-palm-100 flex items-center justify-center">
            <svg
              className="w-6 h-6 text-palm-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
          </div>

          <div>
            <p className="text-warm-gray-700 font-medium">
              {isDragging ? 'Drop files here' : 'Drag and drop files here'}
            </p>
            <p className="text-sm text-warm-gray-500 mt-1">or</p>
          </div>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleBrowseClick}
            disabled={disabled}
          >
            Browse files
          </Button>

          <p className="text-xs text-warm-gray-400 mt-2">
            PDF, DOCX, or TXT up to {formatFileSize(MAX_FILE_SIZE_BYTES)}
          </p>
        </div>
      </div>

      {/* Validation errors */}
      {validationErrors.length > 0 && (
        <div className="mt-4 space-y-2">
          {validationErrors.map((item, index) => (
            <div
              key={`${item.file.name}-${index}`}
              className="flex items-center justify-between p-3 bg-coral-50 border border-coral-200 rounded-sm"
            >
              <div className="flex items-center gap-2 min-w-0">
                <svg
                  className="w-5 h-5 text-coral-500 flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-coral-800 truncate">
                    {item.file.name}
                  </p>
                  <p className="text-xs text-coral-600">{item.error}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => handleRemoveError(index)}
                className="p-1 text-coral-500 hover:text-coral-700 transition-colors"
                aria-label={`Dismiss error for ${item.file.name}`}
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Uploaded files list */}
      {uploadedFiles.length > 0 && (
        <div className="mt-4 space-y-2">
          {uploadedFiles.map((file) => (
            <div
              key={file.id}
              className="flex items-center justify-between p-3 bg-cream-50 border border-cream-300 rounded-sm"
            >
              <div className="flex items-center gap-3 min-w-0 flex-1">
                {/* File icon */}
                <div className="w-8 h-8 rounded bg-palm-100 flex items-center justify-center flex-shrink-0">
                  <svg
                    className="w-4 h-4 text-palm-600"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-warm-gray-800 truncate">
                      {file.name}
                    </p>
                    <span className="text-xs text-warm-gray-500 flex-shrink-0">
                      {formatFileSize(file.size)}
                    </span>
                  </div>

                  {/* Progress bar */}
                  {(file.status === 'uploading' || file.status === 'pending') && (
                    <div className="mt-1.5">
                      <div className="h-1.5 bg-cream-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-palm-500 transition-all duration-300 ease-out"
                          style={{ width: `${file.progress}%` }}
                        />
                      </div>
                      <p className="text-xs text-warm-gray-500 mt-0.5">
                        {file.status === 'pending'
                          ? 'Waiting...'
                          : `Uploading... ${file.progress}%`}
                      </p>
                    </div>
                  )}

                  {/* Complete status */}
                  {file.status === 'complete' && (
                    <p className="text-xs text-palm-600 mt-0.5">Uploaded</p>
                  )}

                  {/* Error status */}
                  {file.status === 'error' && (
                    <p className="text-xs text-coral-600 mt-0.5">
                      {file.error || 'Upload failed'}
                    </p>
                  )}
                </div>
              </div>

              {/* Status indicator / Remove button */}
              <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                {file.status === 'uploading' && (
                  <div className="w-5 h-5">
                    <svg
                      className="animate-spin text-palm-500"
                      viewBox="0 0 24 24"
                      fill="none"
                      aria-hidden="true"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                  </div>
                )}

                {file.status === 'complete' && (
                  <svg
                    className="w-5 h-5 text-palm-500"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                )}

                {onFileRemove && (
                  <button
                    type="button"
                    onClick={() => onFileRemove(file.id)}
                    className="p-1 text-warm-gray-400 hover:text-coral-500 transition-colors"
                    aria-label={`Remove ${file.name}`}
                    disabled={file.status === 'uploading'}
                  >
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export {
  FileUpload,
  type FileUploadProps,
  type UploadedFile,
  MAX_FILE_SIZE_BYTES,
  ALLOWED_EXTENSIONS,
  ALLOWED_MIME_TYPES,
};
