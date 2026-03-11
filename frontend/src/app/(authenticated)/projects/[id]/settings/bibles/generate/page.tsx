'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui';
import { bibleKeys } from '@/hooks/useBibles';

interface TranscriptExtractionResponse {
  id: string;
  name: string;
  slug: string;
  trigger_keywords: string[];
  content_md: string;
  qa_rules: Record<string, unknown[]>;
  is_active: boolean;
  message: string;
}

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

function SparklesIcon({ className }: { className?: string }) {
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
      <path d="M12 3l1.912 5.813a2 2 0 001.275 1.275L21 12l-5.813 1.912a2 2 0 00-1.275 1.275L12 21l-1.912-5.813a2 2 0 00-1.275-1.275L3 12l5.813-1.912a2 2 0 001.275-1.275L12 3z" />
    </svg>
  );
}

function ElapsedTimer() {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(Date.now());

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const timeStr = minutes > 0
    ? `${minutes}:${seconds.toString().padStart(2, '0')}`
    : `${seconds}s`;

  return (
    <div role="status" aria-live="polite" className="bg-cream-100 border border-cream-500 rounded-sm px-4 py-4">
      <div className="flex items-center gap-3">
        <div className="animate-spin rounded-full h-5 w-5 border-2 border-palm-500 border-t-transparent" />
        <div className="flex-1">
          <p className="text-sm font-medium text-warm-gray-700">
            Extracting domain knowledge...
          </p>
          <p className="text-xs text-warm-gray-500 mt-0.5">
            This can take up to 2 minutes for longer transcripts.
          </p>
        </div>
        <span className="text-sm tabular-nums text-warm-gray-400 font-mono">
          {timeStr}
        </span>
      </div>
    </div>
  );
}

export default function GenerateBiblePage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const projectId = params.id as string;

  const [verticalName, setVerticalName] = useState('');
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);

  const generateMutation = useMutation({
    mutationFn: (body: { transcript: string; vertical_name: string }) =>
      apiClient.post<TranscriptExtractionResponse>(
        `/projects/${projectId}/bibles/generate-from-transcript`,
        body,
        { timeout: 180_000 }
      ),
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: bibleKeys.list(projectId),
      });
      if (!data?.id) {
        setError('Generation succeeded but returned invalid data. Check the bibles list.');
        return;
      }
      router.push(`/projects/${projectId}/settings/bibles/${data.id}`);
    },
    onError: (err: Error) => {
      setError(err.message || 'Failed to generate bible. Please try again.');
    },
  });

  const canSubmit =
    verticalName.trim().length > 0 &&
    transcript.trim().length >= 50 &&
    !generateMutation.isPending;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit || isOverLimit) return;
    setError(null);
    generateMutation.mutate({
      transcript: transcript.trim(),
      vertical_name: verticalName.trim(),
    });
  };

  const transcriptCharCount = transcript.length;
  const isOverLimit = transcriptCharCount > 100_000;

  return (
    <div>
      {/* Back link */}
      <Link
        href={`/projects/${projectId}/settings/bibles`}
        className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
      >
        <BackArrowIcon className="w-4 h-4 mr-1" />
        Back to Bibles
      </Link>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-warm-gray-900 mb-1">
          Generate Bible from Transcript
        </h1>
        <p className="text-warm-gray-500 text-sm">
          Paste a domain expert interview and we'll extract structured
          knowledge for content generation and quality checking.
        </p>
      </div>

      <hr className="border-cream-500 mb-6" />

      {/* Form */}
      <form onSubmit={handleSubmit} className="max-w-2xl space-y-6">
        {/* Vertical Name */}
        <div>
          <label
            htmlFor="vertical-name"
            className="block text-sm font-medium text-warm-gray-700 mb-1.5"
          >
            Vertical Name
          </label>
          <input
            id="vertical-name"
            type="text"
            value={verticalName}
            onChange={(e) => {
              setVerticalName(e.target.value);
              if (error) setError(null);
            }}
            placeholder="e.g., Tattoo Cartridge Needles"
            disabled={generateMutation.isPending}
            className="w-full px-3 py-2 border border-cream-500 rounded-sm text-warm-gray-900
                       placeholder:text-warm-gray-400 focus:outline-none focus:ring-2
                       focus:ring-palm-400 focus:border-palm-400 disabled:bg-cream-100
                       disabled:text-warm-gray-500"
          />
          <p className="mt-1 text-xs text-warm-gray-500">
            The name of the domain or product category this knowledge covers.
          </p>
        </div>

        {/* Transcript */}
        <div>
          <label
            htmlFor="transcript"
            className="block text-sm font-medium text-warm-gray-700 mb-1.5"
          >
            Transcript
          </label>
          <textarea
            id="transcript"
            value={transcript}
            onChange={(e) => {
              setTranscript(e.target.value);
              if (error) setError(null);
            }}
            placeholder="Paste your interview transcript here..."
            rows={16}
            disabled={generateMutation.isPending}
            className="w-full px-3 py-2 border border-cream-500 rounded-sm text-warm-gray-900
                       placeholder:text-warm-gray-400 focus:outline-none focus:ring-2
                       focus:ring-palm-400 focus:border-palm-400 disabled:bg-cream-100
                       disabled:text-warm-gray-500 font-mono text-sm resize-y"
          />
          <div className="mt-1 flex items-center justify-between">
            <p className="text-xs text-warm-gray-500">
              Supports raw interview transcripts, including speaker labels and timestamps.
            </p>
            <span
              className={`text-xs ${
                isOverLimit ? 'text-coral-600 font-medium' : 'text-warm-gray-400'
              }`}
            >
              {transcriptCharCount.toLocaleString()} / 100,000
            </span>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div role="alert" className="bg-coral-50 border border-coral-200 rounded-sm px-4 py-3">
            <p className="text-sm text-coral-700">{error}</p>
          </div>
        )}

        {/* Loading state with elapsed timer */}
        {generateMutation.isPending && (
          <ElapsedTimer />
        )}

        {/* Submit button */}
        <div className="flex justify-end">
          <Button
            type="submit"
            disabled={!canSubmit || isOverLimit}
          >
            <SparklesIcon className="w-4 h-4" />
            Generate Draft
          </Button>
        </div>
      </form>
    </div>
  );
}
