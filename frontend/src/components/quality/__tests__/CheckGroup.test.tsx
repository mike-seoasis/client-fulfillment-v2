import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CheckGroup } from '../CheckGroup';

describe('CheckGroup', () => {
  it('renders collapsed when defaultOpen is false', () => {
    render(
      <CheckGroup title="Content Checks" issueCount={0} defaultOpen={false}>
        <div data-testid="child">Child content</div>
      </CheckGroup>
    );
    expect(screen.queryByTestId('child')).toBeNull();
  });

  it('renders expanded when defaultOpen is true', () => {
    render(
      <CheckGroup title="Content Checks" issueCount={2} defaultOpen={true}>
        <div data-testid="child">Child content</div>
      </CheckGroup>
    );
    expect(screen.getByTestId('child')).toBeTruthy();
  });

  it('toggles on click', () => {
    render(
      <CheckGroup title="Content Checks" issueCount={0} defaultOpen={false}>
        <div data-testid="child">Child content</div>
      </CheckGroup>
    );

    // Initially collapsed
    expect(screen.queryByTestId('child')).toBeNull();

    // Click to expand
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByTestId('child')).toBeTruthy();

    // Click to collapse again
    fireEvent.click(screen.getByRole('button'));
    expect(screen.queryByTestId('child')).toBeNull();
  });

  it('shows issue count badge when issueCount > 0', () => {
    render(
      <CheckGroup title="Content Checks" issueCount={3} defaultOpen={true}>
        <div>content</div>
      </CheckGroup>
    );
    expect(screen.getByText('3 issues')).toBeTruthy();
  });

  it('shows singular issue text when issueCount is 1', () => {
    render(
      <CheckGroup title="Content Checks" issueCount={1} defaultOpen={true}>
        <div>content</div>
      </CheckGroup>
    );
    expect(screen.getByText('1 issue')).toBeTruthy();
  });

  it('shows pass badge when issueCount is 0', () => {
    render(
      <CheckGroup title="Content Checks" issueCount={0} defaultOpen={false}>
        <div>content</div>
      </CheckGroup>
    );
    expect(screen.getByText('pass')).toBeTruthy();
  });

  it('shows bible name badge when badge prop is provided', () => {
    render(
      <CheckGroup title="Domain Checks" issueCount={1} badge="Cartridge Needles" defaultOpen={true}>
        <div>content</div>
      </CheckGroup>
    );
    expect(screen.getByText('Cartridge Needles')).toBeTruthy();
  });

  it('has aria-expanded attribute matching open state', () => {
    render(
      <CheckGroup title="Content Checks" issueCount={0} defaultOpen={false}>
        <div>content</div>
      </CheckGroup>
    );
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
  });

  it('does not show badge when badge prop is not provided', () => {
    render(
      <CheckGroup title="Content Checks" issueCount={0} defaultOpen={false}>
        <div>content</div>
      </CheckGroup>
    );
    // Only the title and pass badge should be present
    expect(screen.getByText('Content Checks')).toBeTruthy();
    expect(screen.queryByText('Cartridge Needles')).toBeNull();
  });
});
