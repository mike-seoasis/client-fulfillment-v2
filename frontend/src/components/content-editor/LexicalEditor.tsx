'use client';

import { useEffect, useCallback, useImperativeHandle, forwardRef, useRef, type MutableRefObject } from 'react';
import { LexicalComposer } from '@lexical/react/LexicalComposer';
import { RichTextPlugin } from '@lexical/react/LexicalRichTextPlugin';
import { ContentEditable } from '@lexical/react/LexicalContentEditable';
import { HistoryPlugin } from '@lexical/react/LexicalHistoryPlugin';
import { OnChangePlugin } from '@lexical/react/LexicalOnChangePlugin';
import { ListPlugin } from '@lexical/react/LexicalListPlugin';
import { LexicalErrorBoundary } from '@lexical/react/LexicalErrorBoundary';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { HeadingNode, QuoteNode } from '@lexical/rich-text';
import { ListNode, ListItemNode } from '@lexical/list';
import { $generateNodesFromDOM } from '@lexical/html';
import { $generateHtmlFromNodes } from '@lexical/html';
import { $getRoot, $insertNodes, type EditorState, type LexicalEditor as LexicalEditorType } from 'lexical';
import { HighlightNode } from './HighlightPlugin';

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
};

interface HtmlLoaderProps {
  initialHtml: string;
}

function HtmlLoaderPlugin({ initialHtml }: HtmlLoaderProps) {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    if (!initialHtml) return;

    editor.update(() => {
      const parser = new DOMParser();
      const dom = parser.parseFromString(initialHtml, 'text/html');
      const nodes = $generateNodesFromDOM(editor, dom);
      const root = $getRoot();
      root.clear();
      $insertNodes(nodes);
    });
  }, [editor, initialHtml]);

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
}

export const LexicalEditor = forwardRef<LexicalEditorHandle, LexicalEditorProps>(
  function LexicalEditor({ initialHtml, onChange, className = '' }, ref) {
    const editorRef = useRef<LexicalEditorType | null>(null);

    useImperativeHandle(ref, () => ({
      getHtml: () => {
        let html = '';
        const editor = editorRef.current;
        if (editor) {
          editor.read(() => {
            html = $generateHtmlFromNodes(editor, null);
          });
        }
        return html;
      },
    }));

    const initialConfig = {
      namespace: 'ContentEditor',
      theme,
      nodes: [HeadingNode, QuoteNode, ListNode, ListItemNode, HighlightNode],
      onError: (error: Error) => {
        console.error('Lexical error:', error);
      },
    };

    const handleChange = useCallback(
      (_editorState: EditorState, editor: LexicalEditorType) => {
        if (!onChange) return;
        editor.read(() => {
          const html = $generateHtmlFromNodes(editor, null);
          onChange(html);
        });
      },
      [onChange],
    );

    return (
      <LexicalComposer initialConfig={initialConfig}>
        <div className={`relative ${className}`}>
          <RichTextPlugin
            contentEditable={
              <ContentEditable className="min-h-[200px] outline-none px-4 py-3 text-warm-gray-800 leading-relaxed" />
            }
            placeholder={null}
            ErrorBoundary={LexicalErrorBoundary}
          />
          <HistoryPlugin />
          <ListPlugin />
          <OnChangePlugin onChange={handleChange} ignoreSelectionChange />
          <HtmlLoaderPlugin initialHtml={initialHtml} />
          <EditorRefPlugin editorRef={editorRef} />
        </div>
      </LexicalComposer>
    );
  },
);
