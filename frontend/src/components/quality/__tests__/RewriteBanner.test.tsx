import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RewriteBanner } from '../RewriteBanner';
import type { RewriteResults, VersionsData } from '../QualityPanel';

const baseRewrite: RewriteResults = {
  triggered: true,
  original_score: 52,
  fixed_score: 88,
  issues_sent: 5,
  issues_resolved: 4,
  issues_remaining: 1,
  new_issues_introduced: 0,
  cost_usd: 0.02,
  latency_ms: 800,
  kept_version: 'fixed',
};

const baseVersions: VersionsData = {
  original: { score: 52, content_snapshot: { bottom_description: 'Original text' } },
  fixed: { score: 88, changes_made: ['Removed em-dashes', 'Fixed AI words', 'Rewrote opener'] },
};

describe('RewriteBanner', () => {
  it('renders nothing when triggered is false', () => {
    const rewrite = { ...baseRewrite, triggered: false };
    const { container } = render(
      <RewriteBanner rewrite={rewrite} onViewOriginal={vi.fn()} onViewDiff={vi.fn()} />
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders Auto-Rewrite header when triggered', () => {
    render(
      <RewriteBanner rewrite={baseRewrite} versions={baseVersions} onViewOriginal={vi.fn()} onViewDiff={vi.fn()} />
    );
    expect(screen.getByText('Auto-Rewrite')).toBeTruthy();
  });

  it('shows improved badge when fixed score is higher', () => {
    render(
      <RewriteBanner rewrite={baseRewrite} versions={baseVersions} onViewOriginal={vi.fn()} onViewDiff={vi.fn()} />
    );
    expect(screen.getByText('improved')).toBeTruthy();
  });

  it('shows kept original badge when original was kept', () => {
    const rewrite = { ...baseRewrite, kept_version: 'original' as const, fixed_score: 50 };
    render(
      <RewriteBanner rewrite={rewrite} versions={baseVersions} onViewOriginal={vi.fn()} onViewDiff={vi.fn()} />
    );
    expect(screen.getByText('kept original')).toBeTruthy();
  });

  it('shows skipped badge when there is a skip_reason', () => {
    const rewrite = { ...baseRewrite, skip_reason: 'no_fixable_issues', kept_version: 'original' as const };
    render(
      <RewriteBanner rewrite={rewrite} onViewOriginal={vi.fn()} onViewDiff={vi.fn()} />
    );
    expect(screen.getByText('skipped')).toBeTruthy();
  });

  it('is expanded by default showing score and stats', () => {
    render(
      <RewriteBanner rewrite={baseRewrite} versions={baseVersions} onViewOriginal={vi.fn()} onViewDiff={vi.fn()} />
    );
    expect(screen.getByText('52')).toBeTruthy();
    expect(screen.getByText('88')).toBeTruthy();
    expect(screen.getByText('4')).toBeTruthy(); // resolved count
  });

  it('collapses and shows summary on click', () => {
    render(
      <RewriteBanner rewrite={baseRewrite} versions={baseVersions} onViewOriginal={vi.fn()} onViewDiff={vi.fn()} />
    );
    // Click the header to collapse
    fireEvent.click(screen.getByText('Auto-Rewrite'));
    // Should now show collapsed summary
    expect(screen.getByText(/52 → 88/)).toBeTruthy();
  });

  it('shows changes list when versions are provided', () => {
    render(
      <RewriteBanner rewrite={baseRewrite} versions={baseVersions} onViewOriginal={vi.fn()} onViewDiff={vi.fn()} />
    );
    expect(screen.getByText('Removed em-dashes')).toBeTruthy();
    expect(screen.getByText('Fixed AI words')).toBeTruthy();
    expect(screen.getByText('Rewrote opener')).toBeTruthy();
  });

  it('calls onViewOriginal when View Original is clicked', () => {
    const onViewOriginal = vi.fn();
    render(
      <RewriteBanner rewrite={baseRewrite} versions={baseVersions} onViewOriginal={onViewOriginal} onViewDiff={vi.fn()} />
    );
    fireEvent.click(screen.getByText('View Original'));
    expect(onViewOriginal).toHaveBeenCalledOnce();
  });

  it('calls onViewDiff when View Diff is clicked', () => {
    const onViewDiff = vi.fn();
    render(
      <RewriteBanner rewrite={baseRewrite} versions={baseVersions} onViewOriginal={vi.fn()} onViewDiff={onViewDiff} />
    );
    fireEvent.click(screen.getByText('View Diff'));
    expect(onViewDiff).toHaveBeenCalledOnce();
  });

  it('shows error message when rewrite has error', () => {
    const rewrite = { ...baseRewrite, error: 'LLM API timeout' };
    render(
      <RewriteBanner rewrite={rewrite} onViewOriginal={vi.fn()} onViewDiff={vi.fn()} />
    );
    expect(screen.getByText('LLM API timeout')).toBeTruthy();
  });

  it('shows new issues count when present', () => {
    const rewrite = { ...baseRewrite, new_issues_introduced: 2 };
    render(
      <RewriteBanner rewrite={rewrite} versions={baseVersions} onViewOriginal={vi.fn()} onViewDiff={vi.fn()} />
    );
    expect(screen.getByText('2')).toBeTruthy();
  });
});
