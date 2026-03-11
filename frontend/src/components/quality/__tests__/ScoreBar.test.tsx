import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ScoreBar } from '../ScoreBar';

describe('ScoreBar', () => {
  it('renders with value displayed by default', () => {
    render(<ScoreBar value={0.75} />);
    expect(screen.getByText('0.75')).toBeTruthy();
  });

  it('hides value when showValue is false', () => {
    render(<ScoreBar value={0.75} showValue={false} />);
    expect(screen.queryByText('0.75')).toBeNull();
  });

  it('clamps value to 0-1 range (above 1)', () => {
    render(<ScoreBar value={1.5} />);
    expect(screen.getByText('1.00')).toBeTruthy();
  });

  it('clamps value to 0-1 range (below 0)', () => {
    render(<ScoreBar value={-0.3} />);
    expect(screen.getByText('0.00')).toBeTruthy();
  });

  it('applies palm-500 color for values >= 0.8', () => {
    const { container } = render(<ScoreBar value={0.9} />);
    const bar = container.querySelector('.bg-palm-500');
    expect(bar).toBeTruthy();
  });

  it('applies palm-400 color for values >= 0.7 and < 0.8', () => {
    const { container } = render(<ScoreBar value={0.72} />);
    const bar = container.querySelector('.bg-palm-400');
    expect(bar).toBeTruthy();
  });

  it('applies sand-500 color for values >= 0.5 and < 0.7', () => {
    const { container } = render(<ScoreBar value={0.55} />);
    const bar = container.querySelector('.bg-sand-500');
    expect(bar).toBeTruthy();
  });

  it('applies coral-400 color for values >= 0.3 and < 0.5', () => {
    const { container } = render(<ScoreBar value={0.35} />);
    const bar = container.querySelector('.bg-coral-400');
    expect(bar).toBeTruthy();
  });

  it('applies coral-500 color for values < 0.3', () => {
    const { container } = render(<ScoreBar value={0.1} />);
    const bar = container.querySelector('.bg-coral-500');
    expect(bar).toBeTruthy();
  });

  it('sets correct width percentage', () => {
    const { container } = render(<ScoreBar value={0.65} />);
    const bar = container.querySelector('[style]');
    expect(bar?.getAttribute('style')).toContain('width: 65%');
  });

  it('handles boundary value 0', () => {
    render(<ScoreBar value={0} />);
    expect(screen.getByText('0.00')).toBeTruthy();
  });

  it('handles boundary value 1', () => {
    render(<ScoreBar value={1} />);
    expect(screen.getByText('1.00')).toBeTruthy();
  });
});
