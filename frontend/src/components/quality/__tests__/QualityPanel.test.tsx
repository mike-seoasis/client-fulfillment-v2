import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QualityPanel } from '../QualityPanel';
import type { QaResults } from '../QualityPanel';

describe('QualityPanel', () => {
  it('returns null when qaResults is null', () => {
    const { container } = render(<QualityPanel qaResults={null} />);
    expect(container.innerHTML).toBe('');
  });

  it('shows estimated score when score field is absent', () => {
    const qaResults: QaResults = {
      passed: true,
      issues: [],
      checked_at: new Date().toISOString(),
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.getByText('Estimated Score')).toBeTruthy();
    expect(screen.getByText('100')).toBeTruthy();
  });

  it('shows backend score when score field is present', () => {
    const qaResults: QaResults = {
      passed: true,
      score: 88,
      issues: [],
      checked_at: new Date().toISOString(),
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.getByText('88')).toBeTruthy();
    expect(screen.getByText('Minor Issues')).toBeTruthy();
    expect(screen.queryByText('Estimated Score')).toBeNull();
  });

  it('shows Content Checks group with correct pass/fail for each type', () => {
    const qaResults: QaResults = {
      passed: false,
      issues: [
        { type: 'banned_word', field: 'body', description: 'bad word', context: '...bad word...' },
        { type: 'banned_word', field: 'body', description: 'another', context: '...another...' },
        { type: 'em_dash', field: 'body', description: 'em dash found', context: '...text—more...' },
      ],
    };
    render(<QualityPanel qaResults={qaResults} />);

    expect(screen.getByText('Content Checks')).toBeTruthy();
    // "Banned Words" appears in both CheckRow and FlaggedPassages group header
    expect(screen.getAllByText('Banned Words').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Em Dashes').length).toBeGreaterThanOrEqual(1);
  });

  it('hides Domain Checks group when bibles_matched is absent', () => {
    const qaResults: QaResults = {
      passed: true,
      issues: [],
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.queryByText('Domain Checks')).toBeNull();
  });

  it('shows Domain Checks group when bibles_matched has entries', () => {
    const qaResults: QaResults = {
      passed: true,
      issues: [],
      bibles_matched: ['tattoo-cartridge-needles'],
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.getByText('Domain Checks')).toBeTruthy();
    expect(screen.getByText('Tattoo Cartridge Needles')).toBeTruthy();
  });

  it('shows multiple bibles badge text', () => {
    const qaResults: QaResults = {
      passed: true,
      issues: [],
      bibles_matched: ['cartridge-needles', 'rotary-machines'],
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.getByText('2 bibles')).toBeTruthy();
  });

  it('hides AI Evaluation group when tier2 is absent', () => {
    const qaResults: QaResults = {
      passed: true,
      issues: [],
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.queryByText('AI Evaluation')).toBeNull();
  });

  it('shows AI Evaluation with score bars when tier2 is present', () => {
    const qaResults: QaResults = {
      passed: true,
      score: 92,
      issues: [],
      tier2: {
        model: 'gpt-5.4',
        naturalness: 0.85,
        brief_adherence: 0.72,
        heading_structure: 0.91,
        cost_usd: 0.04,
        latency_ms: 1200,
      },
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.getByText('AI Evaluation')).toBeTruthy();
    expect(screen.getByText('Naturalness')).toBeTruthy();
    expect(screen.getByText('Brief Adherence')).toBeTruthy();
    expect(screen.getByText('Heading Structure')).toBeTruthy();
    expect(screen.getByText('0.85')).toBeTruthy();
  });

  it('handles legacy qa_results format (no score, no tier2, no bibles_matched)', () => {
    const qaResults: QaResults = {
      passed: true,
      issues: [
        { type: 'em_dash', field: 'bottom_description', description: 'dash', context: '...text—more...' },
      ],
    };
    const { container } = render(<QualityPanel qaResults={qaResults} />);
    expect(container.innerHTML).not.toBe('');
    expect(screen.getByText('Estimated Score')).toBeTruthy();
    expect(screen.queryByText('Domain Checks')).toBeNull();
    expect(screen.queryByText('AI Evaluation')).toBeNull();
  });

  it('handles qa_results with empty issues array', () => {
    const qaResults: QaResults = {
      passed: true,
      issues: [],
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.getByText('100')).toBeTruthy();
    expect(screen.getByText('Content Checks')).toBeTruthy();
  });

  it('hides Domain Checks when bibles_matched is empty array', () => {
    const qaResults: QaResults = {
      passed: true,
      issues: [],
      bibles_matched: [],
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.queryByText('Domain Checks')).toBeNull();
  });

  it('clamps backend score to 0-100 range', () => {
    const qaResults: QaResults = {
      passed: true,
      score: 150,
      issues: [],
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.getByText('100')).toBeTruthy();
  });

  it('filters empty strings from bibles_matched', () => {
    const qaResults: QaResults = {
      passed: true,
      issues: [],
      bibles_matched: ['', 'tattoo-needles'],
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.getByText('Tattoo Needles')).toBeTruthy();
    expect(screen.getByText('Domain Checks')).toBeTruthy();
  });

  it('shows short_circuited message when set', () => {
    const qaResults: QaResults = {
      passed: false,
      score: 65,
      score_tier: 'needs_attention',
      short_circuited: true,
      issues: [
        { type: 'tier1_ai_word', field: 'body', description: 'AI word', context: '...delve...' },
      ],
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.getByText('AI evaluation skipped (critical issues found)')).toBeTruthy();
  });

  it('does not show short_circuited message when tier2 data exists', () => {
    const qaResults: QaResults = {
      passed: true,
      score: 92,
      short_circuited: true,
      issues: [],
      tier2: {
        model: 'gpt-4.1',
        naturalness: 0.85,
        brief_adherence: 0.72,
        heading_structure: 0.91,
        cost_usd: 0.04,
        latency_ms: 1200,
      },
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.queryByText('AI evaluation skipped (critical issues found)')).toBeNull();
  });

  it('shows tier2 error message when tier2.error exists', () => {
    const qaResults: QaResults = {
      passed: true,
      score: 85,
      issues: [],
      tier2: {
        model: 'gpt-4.1',
        naturalness: 0,
        brief_adherence: 0,
        heading_structure: 0,
        cost_usd: 0,
        latency_ms: 0,
        error: 'OpenAI API timeout',
      },
    };
    render(<QualityPanel qaResults={qaResults} />);
    expect(screen.getByText('AI Evaluation')).toBeTruthy();
    expect(screen.getByText(/OpenAI API timeout/)).toBeTruthy();
    // Should NOT show score bars when there's an error
    expect(screen.queryByText('Naturalness')).toBeNull();
  });
});
