import { describe, it, expect } from 'vitest';
import { estimateScoreFromIssues, getScoreTier } from '../score-utils';
import type { QaIssue } from '../score-utils';

function makeIssue(type: string): QaIssue {
  return { type, field: 'body', description: '', context: '' };
}

describe('estimateScoreFromIssues', () => {
  it('returns 100 for empty issues list', () => {
    expect(estimateScoreFromIssues([])).toBe(100);
  });

  it('deducts 5 for each critical issue', () => {
    const issues = [
      makeIssue('tier1_ai_word'),
      makeIssue('banned_word'),
    ];
    expect(estimateScoreFromIssues(issues)).toBe(90);
  });

  it('deducts 2 for each warning issue', () => {
    const issues = [
      makeIssue('em_dash'),
      makeIssue('triplet_excess'),
    ];
    expect(estimateScoreFromIssues(issues)).toBe(96);
  });

  it('handles mixed critical and warning issues', () => {
    const issues = [
      makeIssue('banned_word'),       // -5
      makeIssue('competitor_name'),   // -5
      makeIssue('em_dash'),           // -2
    ];
    expect(estimateScoreFromIssues(issues)).toBe(88);
  });

  it('deducts 5 for bible critical issues', () => {
    const issues = [
      makeIssue('bible_banned_claim'),
      makeIssue('bible_wrong_attribution'),
    ];
    expect(estimateScoreFromIssues(issues)).toBe(90);
  });

  it('deducts 2 for bible warning issues', () => {
    const issues = [
      makeIssue('bible_preferred_term'),
      makeIssue('bible_term_context'),
    ];
    expect(estimateScoreFromIssues(issues)).toBe(96);
  });

  it('floors at 0', () => {
    const issues = Array(30).fill(null).map(() => makeIssue('tier1_ai_word'));
    expect(estimateScoreFromIssues(issues)).toBe(0);
  });
});

describe('getScoreTier', () => {
  it('returns publish_ready for 90-100', () => {
    expect(getScoreTier(90)).toBe('publish_ready');
    expect(getScoreTier(100)).toBe('publish_ready');
    expect(getScoreTier(95)).toBe('publish_ready');
  });

  it('returns minor_issues for 70-89', () => {
    expect(getScoreTier(70)).toBe('minor_issues');
    expect(getScoreTier(89)).toBe('minor_issues');
  });

  it('returns needs_attention for 50-69', () => {
    expect(getScoreTier(50)).toBe('needs_attention');
    expect(getScoreTier(69)).toBe('needs_attention');
  });

  it('returns needs_rewrite for 0-49', () => {
    expect(getScoreTier(0)).toBe('needs_rewrite');
    expect(getScoreTier(49)).toBe('needs_rewrite');
  });

  it('returns needs_rewrite for negative scores', () => {
    expect(getScoreTier(-10)).toBe('needs_rewrite');
    expect(getScoreTier(-1)).toBe('needs_rewrite');
  });
});
