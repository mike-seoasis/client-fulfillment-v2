import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Header } from '../Header';

// ============================================================================
// Mock Next.js
// ============================================================================
const mockPathname = vi.fn();

vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname(),
}));

vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// ============================================================================
// Tests
// ============================================================================
describe('Header', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPathname.mockReturnValue('/');
  });

  // ============================================================================
  // Link rendering
  // ============================================================================
  describe('navigation links', () => {
    it('renders Projects link', () => {
      render(<Header />);

      const projectsLink = screen.getByRole('link', { name: 'Projects' });
      expect(projectsLink).toBeInTheDocument();
      expect(projectsLink).toHaveAttribute('href', '/');
    });

    it('renders Reddit link', () => {
      render(<Header />);

      const redditLink = screen.getByRole('link', { name: 'Reddit' });
      expect(redditLink).toBeInTheDocument();
      expect(redditLink).toHaveAttribute('href', '/reddit');
    });

    it('renders the app title', () => {
      render(<Header />);

      expect(screen.getByText('Client Onboarding')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Active states
  // ============================================================================
  describe('active states', () => {
    it('marks Projects link as active on root path', () => {
      mockPathname.mockReturnValue('/');
      render(<Header />);

      const projectsLink = screen.getByRole('link', { name: 'Projects' });
      expect(projectsLink.className).toContain('border-palm-500');
    });

    it('marks Projects link as active on /projects/* paths', () => {
      mockPathname.mockReturnValue('/projects/some-id');
      render(<Header />);

      const projectsLink = screen.getByRole('link', { name: 'Projects' });
      expect(projectsLink.className).toContain('border-palm-500');
    });

    it('marks Reddit link as inactive on root path', () => {
      mockPathname.mockReturnValue('/');
      render(<Header />);

      const redditLink = screen.getByRole('link', { name: 'Reddit' });
      expect(redditLink.className).not.toContain('border-palm-500');
    });

    it('marks Reddit link as active on /reddit path', () => {
      mockPathname.mockReturnValue('/reddit');
      render(<Header />);

      const redditLink = screen.getByRole('link', { name: 'Reddit' });
      expect(redditLink.className).toContain('border-palm-500');
    });

    it('marks Reddit link as active on /reddit/accounts path', () => {
      mockPathname.mockReturnValue('/reddit/accounts');
      render(<Header />);

      const redditLink = screen.getByRole('link', { name: 'Reddit' });
      expect(redditLink.className).toContain('border-palm-500');
    });

    it('marks Projects link as inactive on /reddit path', () => {
      mockPathname.mockReturnValue('/reddit');
      render(<Header />);

      const projectsLink = screen.getByRole('link', { name: 'Projects' });
      // On /reddit, Projects is NOT active since pathname !== '/' and doesn't start with /projects
      expect(projectsLink.className).not.toContain('border-palm-500');
    });
  });
});
