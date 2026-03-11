import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { VersionDiffModal } from '../VersionDiffModal';
import type { VersionsData } from '../QualityPanel';

const versions: VersionsData = {
  original: {
    score: 52,
    content_snapshot: {
      bottom_description: 'Original bottom text with em-dashes and AI words',
    },
  },
  fixed: {
    score: 88,
    changes_made: ['Removed em-dashes', 'Fixed AI words'],
  },
};

const currentFields = {
  page_title: 'My Page',
  meta_description: 'A great page',
  bottom_description: 'Fixed bottom text without issues',
};

describe('VersionDiffModal', () => {
  it('renders with diff mode', () => {
    render(
      <VersionDiffModal
        versions={versions}
        currentFields={currentFields}
        mode="diff"
        onClose={vi.fn()}
        onRestoreOriginal={vi.fn()}
      />
    );
    expect(screen.getByText('Version Comparison')).toBeTruthy();
    expect(screen.getByText('Diff')).toBeTruthy();
    // "Original" appears as both a tab and a label, so use getAllByText
    expect(screen.getAllByText('Original').length).toBeGreaterThanOrEqual(1);
  });

  it('renders with original mode', () => {
    render(
      <VersionDiffModal
        versions={versions}
        currentFields={currentFields}
        mode="original"
        onClose={vi.fn()}
        onRestoreOriginal={vi.fn()}
      />
    );
    expect(screen.getByText('Version Comparison')).toBeTruthy();
    // Should show the original text (stripped of HTML)
    expect(screen.getByText(/Original bottom text with em-dashes/)).toBeTruthy();
  });

  it('shows score comparison', () => {
    render(
      <VersionDiffModal
        versions={versions}
        currentFields={currentFields}
        mode="diff"
        onClose={vi.fn()}
        onRestoreOriginal={vi.fn()}
      />
    );
    expect(screen.getByText('52')).toBeTruthy();
    expect(screen.getByText('88')).toBeTruthy();
  });

  it('switches between diff and original modes', () => {
    render(
      <VersionDiffModal
        versions={versions}
        currentFields={currentFields}
        mode="diff"
        onClose={vi.fn()}
        onRestoreOriginal={vi.fn()}
      />
    );
    // Click "Original" tab — use getAllByText since "Original" appears in multiple places
    const originalButtons = screen.getAllByText('Original');
    // The tab button is the one inside the mode toggle
    const tabButton = originalButtons.find((el) => el.tagName === 'BUTTON');
    fireEvent.click(tabButton!);
    expect(screen.getByText(/Original bottom text with em-dashes/)).toBeTruthy();
  });

  it('calls onClose when Close button is clicked', () => {
    const onClose = vi.fn();
    render(
      <VersionDiffModal
        versions={versions}
        currentFields={currentFields}
        mode="diff"
        onClose={onClose}
        onRestoreOriginal={vi.fn()}
      />
    );
    fireEvent.click(screen.getByText('Close'));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('shows 2-click restore flow', () => {
    const onRestoreOriginal = vi.fn();
    render(
      <VersionDiffModal
        versions={versions}
        currentFields={currentFields}
        mode="diff"
        onClose={vi.fn()}
        onRestoreOriginal={onRestoreOriginal}
      />
    );

    // First click - should show confirmation
    fireEvent.click(screen.getByText('Restore Original'));
    expect(screen.getByText('Are you sure?')).toBeTruthy();
    expect(screen.getByText('Confirm Restore')).toBeTruthy();
    expect(onRestoreOriginal).not.toHaveBeenCalled();

    // Second click - confirms
    fireEvent.click(screen.getByText('Confirm Restore'));
    expect(onRestoreOriginal).toHaveBeenCalledOnce();
  });

  it('cancels restore when Cancel is clicked during confirmation', () => {
    const onRestoreOriginal = vi.fn();
    const onClose = vi.fn();
    render(
      <VersionDiffModal
        versions={versions}
        currentFields={currentFields}
        mode="diff"
        onClose={onClose}
        onRestoreOriginal={onRestoreOriginal}
      />
    );

    // First click starts confirmation
    fireEvent.click(screen.getByText('Restore Original'));
    expect(screen.getByText('Are you sure?')).toBeTruthy();

    // Click Cancel (which becomes Close's label during confirm)
    fireEvent.click(screen.getByText('Cancel'));
    expect(onRestoreOriginal).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('renders field labels from FIELD_LABELS mapping', () => {
    render(
      <VersionDiffModal
        versions={versions}
        currentFields={currentFields}
        mode="diff"
        onClose={vi.fn()}
        onRestoreOriginal={vi.fn()}
      />
    );
    // bottom_description maps to "body" in FIELD_LABELS
    expect(screen.getByText('body')).toBeTruthy();
  });

  it('shows diff legend text in diff mode', () => {
    render(
      <VersionDiffModal
        versions={versions}
        currentFields={currentFields}
        mode="diff"
        onClose={vi.fn()}
        onRestoreOriginal={vi.fn()}
      />
    );
    expect(screen.getByText(/Removed/)).toBeTruthy();
  });

  it('shows original legend text in original mode', () => {
    render(
      <VersionDiffModal
        versions={versions}
        currentFields={currentFields}
        mode="original"
        onClose={vi.fn()}
        onRestoreOriginal={vi.fn()}
      />
    );
    expect(screen.getByText(/Showing original content/)).toBeTruthy();
  });

  it('handles empty content_snapshot gracefully', () => {
    const emptyVersions: VersionsData = {
      original: { score: 50, content_snapshot: {} },
      fixed: { score: 60, changes_made: [] },
    };
    render(
      <VersionDiffModal
        versions={emptyVersions}
        currentFields={{}}
        mode="diff"
        onClose={vi.fn()}
        onRestoreOriginal={vi.fn()}
      />
    );
    expect(screen.getByText('No field snapshots available.')).toBeTruthy();
  });
});
