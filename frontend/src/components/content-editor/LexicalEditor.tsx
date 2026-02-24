'use client';

import { useEffect, useCallback, useImperativeHandle, forwardRef, useRef, type MutableRefObject } from 'react';
import { LexicalComposer } from '@lexical/react/LexicalComposer';
import { RichTextPlugin } from '@lexical/react/LexicalRichTextPlugin';
import { ContentEditable } from '@lexical/react/LexicalContentEditable';
import { HistoryPlugin } from '@lexical/react/LexicalHistoryPlugin';
import { ListPlugin } from '@lexical/react/LexicalListPlugin';
import { LexicalErrorBoundary } from '@lexical/react/LexicalErrorBoundary';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { HeadingNode, QuoteNode } from '@lexical/rich-text';
import { ListNode, ListItemNode } from '@lexical/list';
import { LinkNode } from '@lexical/link';
import { LinkPlugin } from '@lexical/react/LexicalLinkPlugin';
import { TableNode, TableCellNode, TableRowNode } from '@lexical/table';
import { TablePlugin } from '@lexical/react/LexicalTablePlugin';
import { $generateNodesFromDOM } from '@lexical/html';
import { $generateHtmlFromNodes } from '@lexical/html';
import { $getRoot, $insertNodes, type EditorState, type LexicalEditor as LexicalEditorType } from 'lexical';
import { HighlightNode, HighlightPlugin, type TropeRange } from './HighlightPlugin';
import { ToolbarPlugin } from './ToolbarPlugin';

const theme = {
  paragraph: 'mb-3 leading-relaxed text-warm-gray-800',
  heading: {
    h2: 'text-2xl font-semibold text-warm-gray-900 mt-6 mb-3',
    h3: 'text-xl font-semibold text-warm-gray-900 mt-5 mb-2',
  },
  text: {
    bold: 'font-bold',
    italic: 'italic',
  },
  list: {
    ul: 'list-disc ml-6 mb-3 text-warm-gray-800',
    ol: 'list-decimal ml-6 mb-3 text-warm-gray-800',
    listitem: 'mb-1 leading-relaxed',
  },
  link: 'text-lagoon-600 underline hover:text-lagoon-800 cursor-pointer',
  table: 'w-full border-collapse my-4 text-sm',
  tableCell: 'border border-sand-300 px-3 py-2 text-warm-gray-800 text-left align-top',
  tableCellHeader: 'border border-sand-300 px-3 py-2 bg-cream-100 font-semibold text-warm-gray-900 text-left',
  tableRow: '',
};

interface HtmlLoaderProps {
  initialHtml: string;
}

function HtmlLoaderPlugin({ initialHtml }: HtmlLoaderProps) {
  const [editor] = useLexicalComposerContext();
  // Capture initial value in a ref so we only load HTML once per mount.
  // The component is re-keyed when switching back from HTML source view,
  // so a fresh mount always picks up the latest HTML.
  const initialHtmlRef = useRef(initialHtml);

  useEffect(() => {
    const html = initialHtmlRef.current;
    if (!html) return;

    editor.update(() => {
      const parser = new DOMParser();
      const dom = parser.parseFromString(html, 'text/html');
      const nodes = $generateNodesFromDOM(editor, dom);
      const root = $getRoot();
      root.clear();
      $insertNodes(nodes);
    });
  }, [editor]);

  return null;
}

// Strip highlight wrapper spans so exported HTML stays clean
function stripHighlightSpans(html: string): string {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const hlSpans = doc.querySelectorAll('.hl-keyword, .hl-keyword-var, .hl-lsi, .hl-trope');
  hlSpans.forEach((span) => {
    const parent = span.parentNode;
    if (!parent) return;
    while (span.firstChild) {
      parent.insertBefore(span.firstChild, span);
    }
    parent.removeChild(span);
  });
  return doc.body.innerHTML;
}

// Custom OnChangePlugin that skips highlight-plugin tagged updates
function FilteredOnChangePlugin({
  onChange,
  ignoreSelectionChange,
}: {
  onChange: (editorState: EditorState, editor: LexicalEditorType) => void;
  ignoreSelectionChange?: boolean;
}) {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    return editor.registerUpdateListener(({ editorState, tags, dirtyElements, dirtyLeaves }) => {
      if (tags.has('highlight-plugin')) return;
      if (ignoreSelectionChange && dirtyElements.size === 0 && dirtyLeaves.size === 0) return;
      onChange(editorState, editor);
    });
  }, [editor, onChange, ignoreSelectionChange]);

  return null;
}

export interface LexicalEditorHandle {
  getHtml: () => string;
}

function EditorRefPlugin({ editorRef }: { editorRef: MutableRefObject<LexicalEditorType | null> }) {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    editorRef.current = editor;
  }, [editor, editorRef]);

  return null;
}

interface LexicalEditorProps {
  initialHtml: string;
  onChange?: (html: string) => void;
  className?: string;
  primaryKeyword?: string;
  variations?: Set<string>;
  lsiTerms?: string[];
  tropeRanges?: TropeRange[];
}

export const LexicalEditor = forwardRef<LexicalEditorHandle, LexicalEditorProps>(
  function LexicalEditor({ initialHtml, onChange, className = '', primaryKeyword, variations, lsiTerms, tropeRanges }, ref) {
    const editorRef = useRef<LexicalEditorType | null>(null);

    useImperativeHandle(ref, () => ({
      getHtml: () => {
        let html = '';
        const editor = editorRef.current;
        if (editor) {
          editor.read(() => {
            html = stripHighlightSpans($generateHtmlFromNodes(editor, null));
          });
        }
        return html;
      },
    }));

    const initialConfig = {
      namespace: 'ContentEditor',
      theme,
      nodes: [HeadingNode, QuoteNode, ListNode, ListItemNode, LinkNode, TableNode, TableCellNode, TableRowNode, HighlightNode],
      onError: (error: Error) => {
        console.error('Lexical error:', error);
      },
    };

    const handleChange = useCallback(
      (_editorState: EditorState, editor: LexicalEditorType) => {
        if (!onChange) return;
        editor.read(() => {
          const raw = $generateHtmlFromNodes(editor, null);
          onChange(stripHighlightSpans(raw));
        });
      },
      [onChange],
    );

    return (
      <LexicalComposer initialConfig={initialConfig}>
        <div className={`relative ${className}`}>
          <ToolbarPlugin />
          <RichTextPlugin
            contentEditable={
              <ContentEditable className="min-h-[200px] outline-none px-4 py-3 text-warm-gray-800 leading-relaxed" />
            }
            placeholder={null}
            ErrorBoundary={LexicalErrorBoundary}
          />
          <HistoryPlugin />
          <ListPlugin />
          <LinkPlugin />
          <TablePlugin />
          <FilteredOnChangePlugin onChange={handleChange} ignoreSelectionChange />
          <HtmlLoaderPlugin initialHtml={initialHtml} />
          <EditorRefPlugin editorRef={editorRef} />
          {primaryKeyword && variations && lsiTerms && tropeRanges && (
            <HighlightPlugin
              primaryKeyword={primaryKeyword}
              variations={variations}
              lsiTerms={lsiTerms}
              tropeRanges={tropeRanges}
            />
          )}
        </div>
      </LexicalComposer>
    );
  },
);
