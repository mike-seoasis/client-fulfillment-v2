'use client';

import { useState, useRef, useCallback } from 'react';
import { LexicalEditor, type LexicalEditorHandle } from './LexicalEditor';
import type { TropeRange } from './HighlightPlugin';

/**
 * Pretty-print HTML with line breaks between block-level elements.
 * Simple approach: split on `><` boundaries for block tags.
 */
function formatHtml(raw: string): string {
  let html = raw.trim();

  // Add newline after closing block tags followed by opening tags
  // e.g. </p><h2 → </p>\n<h2
  html = html.replace(
    /(<\/(?:h[1-6]|p|div|ul|ol|li|section|article|blockquote)>)\s*(<)/gi,
    '$1\n$2',
  );

  // Add newline before opening block tags if preceded by >
  // e.g. >text</p><p → already handled above, but catch >< without closing tag
  html = html.replace(
    /(>)\s*(<(?:h[1-6]|p|div|ul|ol|li|section|article|blockquote|hr|br)[\s>])/gi,
    '$1\n$2',
  );

  // Add blank line before headings for visual separation
  html = html.replace(/\n(<h[1-6][\s>])/gi, '\n\n$1');

  // Indent list items
  html = html.replace(/\n(<li[\s>])/gi, '\n  $1');

  return html;
}

type ViewMode = 'rendered' | 'html';

interface ContentEditorWithSourceProps {
  initialHtml: string;
  onChange?: (html: string) => void;
  onBlur?: () => void;
  className?: string;
  primaryKeyword?: string;
  variations?: Set<string>;
  lsiTerms?: string[];
  tropeRanges?: TropeRange[];
}

export function ContentEditorWithSource({
  initialHtml,
  onChange,
  onBlur,
  className = '',
  primaryKeyword,
  variations,
  lsiTerms,
  tropeRanges,
}: ContentEditorWithSourceProps) {
  const [activeTab, setActiveTab] = useState<ViewMode>('rendered');
  const [htmlSource, setHtmlSource] = useState(initialHtml);
  const [editorKey, setEditorKey] = useState(0);
  const editorRef = useRef<LexicalEditorHandle>(null);

  const handleEditorChange = useCallback(
    (html: string) => {
      setHtmlSource(html);
      onChange?.(html);
    },
    [onChange],
  );

  const switchToHtmlSource = useCallback(() => {
    if (editorRef.current) {
      const currentHtml = editorRef.current.getHtml();
      setHtmlSource(formatHtml(currentHtml));
    } else {
      setHtmlSource((prev) => formatHtml(prev));
    }
    setActiveTab('html');
  }, []);

  const switchToRendered = useCallback(() => {
    // Strip formatting whitespace before feeding back to Lexical
    const compact = htmlSource.split('\n').map((l) => l.trim()).join('');
    setHtmlSource(compact);
    setEditorKey((k) => k + 1);
    setActiveTab('rendered');
    onChange?.(compact);
  }, [htmlSource, onChange]);

  const handleHtmlSourceChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setHtmlSource(e.target.value);
    },
    [],
  );

  return (
    <div className={className}>
      {/* Tab bar */}
      <div className="flex items-center">
        <button
          type="button"
          onClick={activeTab === 'html' ? switchToRendered : undefined}
          className={`px-3 py-2 text-xs font-medium transition-all ${
            activeTab === 'rendered'
              ? 'text-palm-500 border-b-2 border-palm-500 font-semibold'
              : 'text-warm-500 border-b-2 border-transparent hover:text-warm-700'
          }`}
        >
          Rendered
        </button>
        <button
          type="button"
          onClick={activeTab === 'rendered' ? switchToHtmlSource : undefined}
          className={`px-3 py-2 text-xs font-medium transition-all ${
            activeTab === 'html'
              ? 'text-palm-500 border-b-2 border-palm-500 font-semibold'
              : 'text-warm-500 border-b-2 border-transparent hover:text-warm-700'
          }`}
        >
          HTML Source
        </button>
      </div>

      {/* Rendered view */}
      {activeTab === 'rendered' && (
        <div
          className="px-5 py-4"
          onBlur={(e) => {
            // Only fire onBlur when focus leaves this container entirely
            if (!e.currentTarget.contains(e.relatedTarget as Node)) {
              onBlur?.();
            }
          }}
        >
          <div className="bg-sand-50 border border-sand-300 rounded-sm">
            <LexicalEditor
              key={editorKey}
              ref={editorRef}
              initialHtml={htmlSource}
              onChange={handleEditorChange}
              primaryKeyword={primaryKeyword}
              variations={variations}
              lsiTerms={lsiTerms}
              tropeRanges={tropeRanges}
            />
          </div>
        </div>
      )}

      {/* HTML Source view */}
      {activeTab === 'html' && (
        <div className="px-5 py-4">
          <textarea
            value={htmlSource}
            onChange={handleHtmlSourceChange}
            onBlur={onBlur}
            rows={20}
            className="w-full px-4 py-3 text-sm font-mono bg-warm-50 text-warm-800 border border-sand-400 rounded-sm focus:outline-none focus:ring-2 focus:ring-palm-400/30 transition-all resize-y leading-loose"
          />
        </div>
      )}
    </div>
  );
}
