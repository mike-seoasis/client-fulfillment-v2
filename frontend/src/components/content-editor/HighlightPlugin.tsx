'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import {
  $getRoot,
  $isTextNode,
  $createTextNode,
  ElementNode,
  type LexicalNode,
  type NodeKey,
  type SerializedElementNode,
  type Spread,
  type TextNode,
  type LexicalUpdateJSON,
} from 'lexical';

// ---------------------------------------------------------------------------
// Highlight types
// ---------------------------------------------------------------------------

export const HL_KEYWORD = 'hl-keyword';
export const HL_KEYWORD_VAR = 'hl-keyword-var';
export const HL_LSI = 'hl-lsi';
export const HL_TROPE = 'hl-trope';

type HighlightType = typeof HL_KEYWORD | typeof HL_KEYWORD_VAR | typeof HL_LSI | typeof HL_TROPE;

// ---------------------------------------------------------------------------
// HighlightNode — custom inline ElementNode wrapping highlighted text
// ---------------------------------------------------------------------------

type SerializedHighlightNode = Spread<
  { highlightType: string },
  SerializedElementNode
>;

export class HighlightNode extends ElementNode {
  __highlightType: string;

  static getType(): string {
    return 'highlight';
  }

  static clone(node: HighlightNode): HighlightNode {
    return new HighlightNode(node.__highlightType, node.__key);
  }

  constructor(highlightType: string, key?: NodeKey) {
    super(key);
    this.__highlightType = highlightType;
  }

  createDOM(): HTMLElement {
    const span = document.createElement('span');
    span.className = this.__highlightType;
    return span;
  }

  updateDOM(prevNode: this, dom: HTMLElement): boolean {
    if (prevNode.__highlightType !== this.__highlightType) {
      dom.className = this.__highlightType;
    }
    return false;
  }

  static importJSON(json: SerializedHighlightNode): HighlightNode {
    return $createHighlightNode(json.highlightType as HighlightType);
  }

  updateFromJSON(json: LexicalUpdateJSON<SerializedHighlightNode>): this {
    return super.updateFromJSON(json);
  }

  exportJSON(): SerializedHighlightNode {
    return {
      ...super.exportJSON(),
      highlightType: this.__highlightType,
    };
  }

  // Mark as inline so it renders inside paragraphs/headings
  isInline(): boolean {
    return true;
  }

  canInsertTextBefore(): boolean {
    return false;
  }

  canInsertTextAfter(): boolean {
    return false;
  }

  canBeEmpty(): boolean {
    return false;
  }

  // Exclude from clipboard so highlights aren't pasted
  excludeFromCopy(): boolean {
    return true;
  }

  getHighlightType(): string {
    return this.getLatest().__highlightType;
  }
}

export function $createHighlightNode(highlightType: HighlightType): HighlightNode {
  return new HighlightNode(highlightType);
}

export function $isHighlightNode(
  node: LexicalNode | null | undefined,
): node is HighlightNode {
  return node instanceof HighlightNode;
}

// ---------------------------------------------------------------------------
// Plugin props
// ---------------------------------------------------------------------------

export interface TropeRange {
  text: string;
}

interface HighlightPluginProps {
  primaryKeyword: string;
  variations: Set<string>;
  lsiTerms: string[];
  tropeRanges: TropeRange[];
}

// ---------------------------------------------------------------------------
// Regex builders
// ---------------------------------------------------------------------------

function buildTermRegex(terms: string[]): RegExp | null {
  const escaped = terms
    .filter(Boolean)
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (escaped.length === 0) return null;
  // Sort longest first so multi-word terms match before single words
  escaped.sort((a, b) => b.length - a.length);
  return new RegExp(`\\b(${escaped.join('|')})\\b`, 'gi');
}

function buildTropeRegex(tropeTexts: string[]): RegExp | null {
  const escaped = tropeTexts
    .filter(Boolean)
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (escaped.length === 0) return null;
  escaped.sort((a, b) => b.length - a.length);
  // No word boundaries — trope matches are exact substring matches
  return new RegExp(`(${escaped.join('|')})`, 'gi');
}

// ---------------------------------------------------------------------------
// Match finding
// ---------------------------------------------------------------------------

interface MatchRange {
  start: number;
  end: number;
  hlType: HighlightType;
}

function findMatches(
  text: string,
  keywordRegex: RegExp | null,
  varRegex: RegExp | null,
  lsiRegex: RegExp | null,
  tropeRegex: RegExp | null,
): MatchRange[] {
  const ranges: MatchRange[] = [];

  const addMatches = (regex: RegExp | null, hlType: HighlightType) => {
    if (!regex) return;
    regex.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = regex.exec(text)) !== null) {
      ranges.push({ start: m.index, end: m.index + m[0].length, hlType });
    }
  };

  // Priority order: keyword > var > lsi > trope
  addMatches(keywordRegex, HL_KEYWORD);
  addMatches(varRegex, HL_KEYWORD_VAR);
  addMatches(lsiRegex, HL_LSI);
  addMatches(tropeRegex, HL_TROPE);

  // Sort by position, then by priority
  const priority: Record<string, number> = {
    [HL_KEYWORD]: 0,
    [HL_KEYWORD_VAR]: 1,
    [HL_LSI]: 2,
    [HL_TROPE]: 3,
  };
  ranges.sort((a, b) => {
    if (a.start !== b.start) return a.start - b.start;
    return priority[a.hlType] - priority[b.hlType];
  });

  // Remove overlapping lower-priority ranges
  const result: MatchRange[] = [];
  for (const range of ranges) {
    const overlaps = result.some(
      (r) => range.start < r.end && range.end > r.start,
    );
    if (!overlaps) {
      result.push(range);
    }
  }

  return result.sort((a, b) => a.start - b.start);
}

// ---------------------------------------------------------------------------
// Tree traversal helpers
// ---------------------------------------------------------------------------

function collectTextNodes(node: LexicalNode): TextNode[] {
  const result: TextNode[] = [];
  const queue: LexicalNode[] = [node];
  while (queue.length > 0) {
    const current = queue.shift()!;
    if ($isTextNode(current)) {
      result.push(current);
    } else if ('getChildren' in current && typeof current.getChildren === 'function') {
      queue.push(
        ...(current as { getChildren: () => LexicalNode[] }).getChildren(),
      );
    }
  }
  return result;
}

function clearHighlights(node: LexicalNode): void {
  const queue: LexicalNode[] = [node];
  while (queue.length > 0) {
    const current = queue.shift()!;
    if ($isHighlightNode(current)) {
      const children = current.getChildren();
      for (const child of children) {
        current.insertBefore(child);
      }
      current.remove();
      queue.push(...children);
      continue;
    }
    if ('getChildren' in current && typeof current.getChildren === 'function') {
      queue.push(
        ...(current as { getChildren: () => LexicalNode[] }).getChildren(),
      );
    }
  }
}

// ---------------------------------------------------------------------------
// Core highlight application
// ---------------------------------------------------------------------------

function applyHighlights(
  primaryKeyword: string,
  variations: Set<string>,
  lsiTerms: string[],
  tropeRanges: TropeRange[],
): void {
  const root = $getRoot();

  // 1. Clear existing highlights
  clearHighlights(root);

  // 2. Build regexes
  const kwLower = primaryKeyword.trim().toLowerCase();
  const keywordRegex = kwLower ? buildTermRegex([kwLower]) : null;
  const varRegex = buildTermRegex(Array.from(variations));
  const lsiRegex = buildTermRegex(lsiTerms);
  const tropeRegex = buildTropeRegex(tropeRanges.map((r) => r.text));

  // 3. Collect text nodes (fresh after clearing)
  const textNodes = collectTextNodes(root);

  // 4. Process each text node in reverse to avoid index issues
  for (let i = textNodes.length - 1; i >= 0; i--) {
    const textNode = textNodes[i];
    if (!textNode.isAttached()) continue;

    const text = textNode.getTextContent();
    if (!text) continue;

    const matches = findMatches(text, keywordRegex, varRegex, lsiRegex, tropeRegex);
    if (matches.length === 0) continue;

    // Build segments
    const segments: { text: string; hlType: HighlightType | null }[] = [];
    let cursor = 0;
    for (const match of matches) {
      if (match.start > cursor) {
        segments.push({ text: text.slice(cursor, match.start), hlType: null });
      }
      segments.push({
        text: text.slice(match.start, match.end),
        hlType: match.hlType,
      });
      cursor = match.end;
    }
    if (cursor < text.length) {
      segments.push({ text: text.slice(cursor), hlType: null });
    }

    // Replace text node with segments
    const format = textNode.getFormat();
    const style = textNode.getStyle();

    let anchorNode: LexicalNode = textNode;
    let isFirst = true;

    for (const segment of segments) {
      const newText = $createTextNode(segment.text);
      newText.setFormat(format);
      if (style) newText.setStyle(style);

      let nodeToInsert: LexicalNode;
      if (segment.hlType) {
        const hlNode = $createHighlightNode(segment.hlType);
        hlNode.append(newText);
        nodeToInsert = hlNode;
      } else {
        nodeToInsert = newText;
      }

      if (isFirst) {
        textNode.replace(nodeToInsert);
        isFirst = false;
      } else {
        anchorNode.insertAfter(nodeToInsert);
      }
      anchorNode = nodeToInsert;
    }
  }
}

// ---------------------------------------------------------------------------
// CSS injection
// ---------------------------------------------------------------------------

function injectHighlightStyles(container: HTMLElement): () => void {
  const styleId = 'lexical-highlight-styles';
  if (container.querySelector(`#${styleId}`)) return () => {};

  const style = document.createElement('style');
  style.id = styleId;
  style.textContent = `
    .${HL_KEYWORD} {
      background: linear-gradient(to bottom, rgba(238, 200, 70, 0.0) 50%, rgba(238, 200, 70, 0.35) 50%);
      padding: 0 1px;
    }
    .${HL_KEYWORD_VAR} {
      background: linear-gradient(to bottom, rgba(238, 200, 70, 0.0) 50%, rgba(238, 200, 70, 0.2) 50%);
      padding: 0 1px;
      border-bottom: 1px dashed rgba(180, 155, 50, 0.4);
    }
    .${HL_LSI} {
      background: rgba(42, 157, 143, 0.14);
      border-bottom: 2px solid rgba(42, 157, 143, 0.45);
      padding: 0 1px;
    }
    .${HL_TROPE} {
      text-decoration: underline wavy #E07A5F;
      text-decoration-thickness: 2px;
      text-underline-offset: 3px;
    }
  `;
  container.prepend(style);

  return () => {
    style.remove();
  };
}

// ---------------------------------------------------------------------------
// React Plugin Component
// ---------------------------------------------------------------------------

export function HighlightPlugin({
  primaryKeyword,
  variations,
  lsiTerms,
  tropeRanges,
}: HighlightPluginProps) {
  const [editor] = useLexicalComposerContext();
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isApplyingRef = useRef(false);

  const doHighlight = useCallback(() => {
    if (isApplyingRef.current) return;
    isApplyingRef.current = true;

    editor.update(
      () => {
        applyHighlights(primaryKeyword, variations, lsiTerms, tropeRanges);
      },
      { tag: 'highlight-plugin' },
    );

    isApplyingRef.current = false;
  }, [editor, primaryKeyword, variations, lsiTerms, tropeRanges]);

  // Inject CSS styles into the editor container
  useEffect(() => {
    const rootElement = editor.getRootElement();
    if (!rootElement) return;
    const container = rootElement.parentElement;
    if (!container) return;
    return injectHighlightStyles(container);
  }, [editor]);

  // Warn if HighlightNode is not registered
  useEffect(() => {
    if (!editor.hasNodes([HighlightNode])) {
      console.warn(
        'HighlightPlugin: HighlightNode is not registered. ' +
          'Add HighlightNode to the nodes array in your LexicalComposer initialConfig.',
      );
    }
  }, [editor]);

  // Listen for editor updates and recompute highlights with 200ms debounce
  useEffect(() => {
    // Apply initial highlights
    doHighlight();

    const removeListener = editor.registerUpdateListener(({ tags }) => {
      // Skip updates triggered by our own highlight application
      if (tags.has('highlight-plugin')) return;

      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      debounceTimerRef.current = setTimeout(() => {
        doHighlight();
      }, 200);
    });

    return () => {
      removeListener();
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [editor, doHighlight]);

  return null;
}
