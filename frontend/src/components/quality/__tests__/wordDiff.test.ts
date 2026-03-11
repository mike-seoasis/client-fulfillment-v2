import { describe, it, expect } from 'vitest';
import { wordDiff } from '../VersionDiffModal';

describe('wordDiff', () => {
  it('returns empty array for two empty strings', () => {
    expect(wordDiff('', '')).toEqual([]);
  });

  it('returns equal segment when strings are identical', () => {
    const result = wordDiff('hello world', 'hello world');
    expect(result).toEqual([{ type: 'equal', text: 'hello world' }]);
  });

  it('returns added segment when original is empty', () => {
    const result = wordDiff('', 'hello world');
    expect(result).toEqual([{ type: 'added', text: 'hello world' }]);
  });

  it('returns removed segment when modified is empty', () => {
    const result = wordDiff('hello world', '');
    expect(result).toEqual([{ type: 'removed', text: 'hello world' }]);
  });

  it('detects word substitution', () => {
    const result = wordDiff('the quick brown fox', 'the fast brown fox');
    const types = result.map((s) => s.type);
    expect(types).toContain('removed');
    expect(types).toContain('added');
    // "the " and " brown fox" should be equal
    const equalParts = result.filter((s) => s.type === 'equal');
    expect(equalParts.length).toBeGreaterThanOrEqual(2);
  });

  it('detects word addition', () => {
    const result = wordDiff('hello world', 'hello beautiful world');
    const added = result.filter((s) => s.type === 'added');
    expect(added.length).toBeGreaterThanOrEqual(1);
    const addedText = added.map((s) => s.text.trim()).join(' ');
    expect(addedText).toContain('beautiful');
  });

  it('detects word removal', () => {
    const result = wordDiff('hello beautiful world', 'hello world');
    const removed = result.filter((s) => s.type === 'removed');
    expect(removed.length).toBeGreaterThanOrEqual(1);
    const removedText = removed.map((s) => s.text.trim()).join(' ');
    expect(removedText).toContain('beautiful');
  });

  it('handles complete replacement', () => {
    const result = wordDiff('abc def', 'xyz uvw');
    const removed = result.filter((s) => s.type === 'removed');
    const added = result.filter((s) => s.type === 'added');
    expect(removed.length).toBeGreaterThanOrEqual(1);
    expect(added.length).toBeGreaterThanOrEqual(1);
  });

  it('handles multi-word changes', () => {
    const result = wordDiff(
      'The cat sat on the mat',
      'The dog stood on the rug'
    );
    // Should have equal parts ("The ", " on the ") and changed parts
    const equal = result.filter((s) => s.type === 'equal');
    expect(equal.length).toBeGreaterThanOrEqual(2);
  });

  it('preserves whitespace in segments', () => {
    const result = wordDiff('a b c', 'a b c');
    expect(result).toEqual([{ type: 'equal', text: 'a b c' }]);
  });

  it('merges consecutive same-type segments', () => {
    // If multiple consecutive words are removed, they should be merged
    const result = wordDiff('keep remove1 remove2 keep2', 'keep keep2');
    for (let i = 1; i < result.length; i++) {
      if (result[i].type === result[i - 1].type) {
        // Consecutive same types should not happen (they should be merged)
        expect(true).toBe(false);
      }
    }
  });
});
