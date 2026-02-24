'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import {
  $getSelection,
  $setSelection,
  $isRangeSelection,
  CAN_UNDO_COMMAND,
  CAN_REDO_COMMAND,
  FORMAT_TEXT_COMMAND,
  UNDO_COMMAND,
  REDO_COMMAND,
  COMMAND_PRIORITY_LOW,
  $createParagraphNode,
  type RangeSelection,
} from 'lexical';
import { $setBlocksType } from '@lexical/selection';
import { $createHeadingNode, $createQuoteNode, $isHeadingNode } from '@lexical/rich-text';
import {
  INSERT_ORDERED_LIST_COMMAND,
  INSERT_UNORDERED_LIST_COMMAND,
  REMOVE_LIST_COMMAND,
  $isListNode,
  $isListItemNode,
  ListNode,
} from '@lexical/list';
import { $isLinkNode, TOGGLE_LINK_COMMAND } from '@lexical/link';
import { $getNearestNodeOfType } from '@lexical/utils';
import type { HeadingTagType } from '@lexical/rich-text';

type BlockType = 'paragraph' | 'h2' | 'h3' | 'quote' | 'ul' | 'ol';

const BLOCK_TYPE_LABELS: Record<BlockType, string> = {
  paragraph: 'Paragraph',
  h2: 'Heading 2',
  h3: 'Heading 3',
  quote: 'Quote',
  ul: 'Bulleted List',
  ol: 'Numbered List',
};

export function ToolbarPlugin() {
  const [editor] = useLexicalComposerContext();
  const [activeBlock, setActiveBlock] = useState<BlockType>('paragraph');
  const [isBold, setIsBold] = useState(false);
  const [isItalic, setIsItalic] = useState(false);
  const [isLink, setIsLink] = useState(false);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [showLinkInput, setShowLinkInput] = useState(false);
  const [linkUrl, setLinkUrl] = useState('');
  const linkInputRef = useRef<HTMLInputElement>(null);
  // Save selection before opening the link input (focus moves away from editor)
  const savedSelectionRef = useRef<RangeSelection | null>(null);

  // Track selection state
  useEffect(() => {
    return editor.registerUpdateListener(({ editorState }) => {
      editorState.read(() => {
        const selection = $getSelection();
        if (!$isRangeSelection(selection)) return;

        // Text format
        setIsBold(selection.hasFormat('bold'));
        setIsItalic(selection.hasFormat('italic'));

        // Link detection
        const node = selection.anchor.getNode();
        const parent = node.getParent();
        setIsLink($isLinkNode(parent) || $isLinkNode(node));

        // Block type
        const anchorNode = selection.anchor.getNode();
        let element =
          anchorNode.getKey() === 'root'
            ? anchorNode
            : anchorNode.getTopLevelElementOrThrow();

        // If we're inside a list item, walk up to the list node
        if ($isListItemNode(element) || $isListItemNode(anchorNode)) {
          const list = $getNearestNodeOfType<ListNode>(anchorNode, ListNode);
          if (list) {
            element = list;
          }
        }

        if ($isHeadingNode(element)) {
          setActiveBlock(element.getTag() as BlockType);
        } else if ($isListNode(element)) {
          setActiveBlock(element.getListType() === 'bullet' ? 'ul' : 'ol');
        } else {
          const type = element.getType();
          if (type === 'quote') {
            setActiveBlock('quote');
          } else {
            setActiveBlock('paragraph');
          }
        }
      });
    });
  }, [editor]);

  // Track undo/redo availability
  useEffect(() => {
    const unregUndo = editor.registerCommand(
      CAN_UNDO_COMMAND,
      (payload) => {
        setCanUndo(payload);
        return false;
      },
      COMMAND_PRIORITY_LOW,
    );
    const unregRedo = editor.registerCommand(
      CAN_REDO_COMMAND,
      (payload) => {
        setCanRedo(payload);
        return false;
      },
      COMMAND_PRIORITY_LOW,
    );
    return () => {
      unregUndo();
      unregRedo();
    };
  }, [editor]);

  const formatBlock = useCallback(
    (type: BlockType) => {
      editor.update(() => {
        const selection = $getSelection();
        if (!$isRangeSelection(selection)) return;

        if (type === 'paragraph') {
          $setBlocksType(selection, () => $createParagraphNode());
        } else if (type === 'h2' || type === 'h3') {
          $setBlocksType(selection, () => $createHeadingNode(type as HeadingTagType));
        } else if (type === 'quote') {
          $setBlocksType(selection, () => $createQuoteNode());
        } else if (type === 'ul') {
          if (activeBlock === 'ul') {
            editor.dispatchCommand(REMOVE_LIST_COMMAND, undefined);
          } else {
            editor.dispatchCommand(INSERT_UNORDERED_LIST_COMMAND, undefined);
          }
        } else if (type === 'ol') {
          if (activeBlock === 'ol') {
            editor.dispatchCommand(REMOVE_LIST_COMMAND, undefined);
          } else {
            editor.dispatchCommand(INSERT_ORDERED_LIST_COMMAND, undefined);
          }
        }
      });
      // Refocus editor after block type change
      editor.focus();
    },
    [editor, activeBlock],
  );

  const handleLink = useCallback(() => {
    if (isLink) {
      editor.dispatchCommand(TOGGLE_LINK_COMMAND, null);
    } else {
      // Save the current selection before focus leaves the editor
      editor.getEditorState().read(() => {
        const selection = $getSelection();
        if ($isRangeSelection(selection)) {
          savedSelectionRef.current = selection.clone() as RangeSelection;
        }
      });
      setLinkUrl('');
      setShowLinkInput(true);
      setTimeout(() => linkInputRef.current?.focus(), 0);
    }
  }, [editor, isLink]);

  const submitLink = useCallback(() => {
    if (linkUrl.trim()) {
      let url = linkUrl.trim();
      if (!url.startsWith('/') && !url.startsWith('#') && !url.match(/^https?:\/\//)) {
        url = 'https://' + url;
      }
      // Restore selection, then apply link
      editor.update(() => {
        const saved = savedSelectionRef.current;
        if (saved) {
          $setSelection(saved.clone());
        }
      });
      // Dispatch after selection is restored
      setTimeout(() => {
        editor.dispatchCommand(TOGGLE_LINK_COMMAND, url);
        editor.focus();
      }, 0);
    }
    setShowLinkInput(false);
    setLinkUrl('');
    savedSelectionRef.current = null;
  }, [editor, linkUrl]);

  const cancelLink = useCallback(() => {
    setShowLinkInput(false);
    setLinkUrl('');
    savedSelectionRef.current = null;
    editor.focus();
  }, [editor]);

  // Prevent toolbar buttons from stealing editor focus
  const preventFocusLoss = (e: React.MouseEvent) => e.preventDefault();

  const doUndo = useCallback(() => {
    editor.focus();
    // Small delay to ensure focus is restored before dispatching
    requestAnimationFrame(() => {
      editor.dispatchCommand(UNDO_COMMAND, undefined);
    });
  }, [editor]);

  const doRedo = useCallback(() => {
    editor.focus();
    requestAnimationFrame(() => {
      editor.dispatchCommand(REDO_COMMAND, undefined);
    });
  }, [editor]);

  const btnBase =
    'p-1.5 rounded-sm transition-colors text-warm-500 hover:text-warm-800 hover:bg-sand-100';
  const btnActive = 'text-palm-700 bg-palm-50 hover:text-palm-800 hover:bg-palm-100';

  return (
    <div className="border-b border-sand-200 bg-sand-50/60">
      <div className="flex items-center gap-0.5 px-2 py-1.5 flex-wrap">
        {/* Block type selector */}
        <select
          value={activeBlock}
          onChange={(e) => formatBlock(e.target.value as BlockType)}
          className="text-xs font-medium text-warm-700 bg-white border border-sand-300 rounded-sm px-2 py-1.5 mr-1.5 focus:outline-none focus:ring-1 focus:ring-palm-400 cursor-pointer"
        >
          {Object.entries(BLOCK_TYPE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>

        {/* Divider */}
        <div className="w-px h-5 bg-sand-300 mx-1" />

        {/* Bold */}
        <button
          type="button"
          onMouseDown={preventFocusLoss}
          onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'bold')}
          className={`${btnBase} ${isBold ? btnActive : ''}`}
          title="Bold (Ctrl+B)"
          aria-label="Bold"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M15.6 10.79c.97-.67 1.65-1.77 1.65-2.79 0-2.26-1.75-4-4-4H7v14h7.04c2.09 0 3.71-1.7 3.71-3.79 0-1.52-.86-2.82-2.15-3.42zM10 6.5h3c.83 0 1.5.67 1.5 1.5s-.67 1.5-1.5 1.5h-3v-3zm3.5 9H10v-3h3.5c.83 0 1.5.67 1.5 1.5s-.67 1.5-1.5 1.5z" />
          </svg>
        </button>

        {/* Italic */}
        <button
          type="button"
          onMouseDown={preventFocusLoss}
          onClick={() => editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'italic')}
          className={`${btnBase} ${isItalic ? btnActive : ''}`}
          title="Italic (Ctrl+I)"
          aria-label="Italic"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M10 4v3h2.21l-3.42 8H6v3h8v-3h-2.21l3.42-8H18V4z" />
          </svg>
        </button>

        {/* Divider */}
        <div className="w-px h-5 bg-sand-300 mx-1" />

        {/* Link */}
        <button
          type="button"
          onMouseDown={preventFocusLoss}
          onClick={handleLink}
          className={`${btnBase} ${isLink ? btnActive : ''}`}
          title={isLink ? 'Remove Link' : 'Insert Link'}
          aria-label={isLink ? 'Remove Link' : 'Insert Link'}
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z" />
          </svg>
        </button>

        {/* Divider */}
        <div className="w-px h-5 bg-sand-300 mx-1" />

        {/* Bullet list */}
        <button
          type="button"
          onMouseDown={preventFocusLoss}
          onClick={() => formatBlock('ul')}
          className={`${btnBase} ${activeBlock === 'ul' ? btnActive : ''}`}
          title="Bulleted List"
          aria-label="Bulleted List"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M4 10.5c-.83 0-1.5.67-1.5 1.5s.67 1.5 1.5 1.5 1.5-.67 1.5-1.5-.67-1.5-1.5-1.5zm0-6c-.83 0-1.5.67-1.5 1.5S3.17 7.5 4 7.5 5.5 6.83 5.5 6 4.83 4.5 4 4.5zm0 12c-.83 0-1.5.68-1.5 1.5s.68 1.5 1.5 1.5 1.5-.68 1.5-1.5-.67-1.5-1.5-1.5zM7 19h14v-2H7v2zm0-6h14v-2H7v2zm0-8v2h14V5H7z" />
          </svg>
        </button>

        {/* Numbered list */}
        <button
          type="button"
          onMouseDown={preventFocusLoss}
          onClick={() => formatBlock('ol')}
          className={`${btnBase} ${activeBlock === 'ol' ? btnActive : ''}`}
          title="Numbered List"
          aria-label="Numbered List"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M2 17h2v.5H3v1h1v.5H2v1h3v-4H2v1zm1-9h1V4H2v1h1v3zm-1 3h1.8L2 13.1v.9h3v-1H3.2L5 10.9V10H2v1zm5-6v2h14V5H7zm0 14h14v-2H7v2zm0-6h14v-2H7v2z" />
          </svg>
        </button>

        {/* Divider */}
        <div className="w-px h-5 bg-sand-300 mx-1" />

        {/* Undo */}
        <button
          type="button"
          onMouseDown={(e) => {
            e.preventDefault();
            doUndo();
          }}
          className={`${btnBase} ${!canUndo ? 'opacity-30' : ''}`}
          title="Undo (Ctrl+Z)"
          aria-label="Undo"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z" />
          </svg>
        </button>

        {/* Redo */}
        <button
          type="button"
          onMouseDown={(e) => {
            e.preventDefault();
            doRedo();
          }}
          className={`${btnBase} ${!canRedo ? 'opacity-30' : ''}`}
          title="Redo (Ctrl+Shift+Z)"
          aria-label="Redo"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M18.4 10.6C16.55 8.99 14.15 8 11.5 8c-4.65 0-8.58 3.03-9.96 7.22L3.9 16c1.05-3.19 4.05-5.5 7.6-5.5 1.95 0 3.73.72 5.12 1.88L13 16h9V7l-3.6 3.6z" />
          </svg>
        </button>
      </div>

      {/* Link URL input bar */}
      {showLinkInput && (
        <div className="flex items-center gap-2 px-3 py-2 border-t border-sand-200 bg-white">
          <svg className="w-3.5 h-3.5 text-warm-400 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z" />
          </svg>
          <input
            ref={linkInputRef}
            type="text"
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                submitLink();
              }
              if (e.key === 'Escape') cancelLink();
            }}
            placeholder="Enter URL (e.g. /collections/shoes or https://...)"
            className="flex-1 text-xs text-warm-800 bg-transparent outline-none placeholder:text-warm-400"
          />
          <span className="text-[10px] text-warm-400 flex-shrink-0">Enter to apply</span>
          <button
            type="button"
            onClick={cancelLink}
            className="text-xs text-warm-400 hover:text-warm-600 px-1 py-1 transition-colors"
          >
            Esc
          </button>
        </div>
      )}
    </div>
  );
}
