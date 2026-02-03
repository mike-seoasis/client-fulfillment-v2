import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ProjectCard } from '../ProjectCard';
import type { Project } from '@/hooks/use-projects';

// Mock next/navigation
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

// Sample project data for tests
const mockProject: Project = {
  id: 'proj-123',
  name: 'Test Project',
  site_url: 'https://example.com',
  client_id: null,
  additional_info: null,
  status: 'active',
  phase_status: {},
  brand_config_status: 'pending',
  has_brand_config: false,
  uploaded_files_count: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-15T10:30:00Z',
};

describe('ProjectCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the project name', () => {
      render(<ProjectCard project={mockProject} />);

      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });

    it('renders the site URL', () => {
      render(<ProjectCard project={mockProject} />);

      expect(screen.getByText('https://example.com')).toBeInTheDocument();
    });

    it('renders placeholder metrics', () => {
      render(<ProjectCard project={mockProject} />);

      expect(screen.getByText('0 pages')).toBeInTheDocument();
      expect(screen.getByText('0 clusters')).toBeInTheDocument();
      expect(screen.getByText('0 pending')).toBeInTheDocument();
    });

    it('renders relative last activity time', () => {
      render(<ProjectCard project={mockProject} />);

      // The text will be something like "Last activity 2 weeks ago"
      expect(screen.getByText(/Last activity/)).toBeInTheDocument();
    });
  });

  describe('navigation', () => {
    it('navigates to project detail on click', async () => {
      const user = userEvent.setup();
      render(<ProjectCard project={mockProject} />);

      // Card has role="button" when onClick is provided
      const card = screen.getByRole('button');
      await user.click(card);

      expect(mockPush).toHaveBeenCalledWith('/projects/proj-123');
    });

    it('navigates on keyboard Enter', async () => {
      const user = userEvent.setup();
      render(<ProjectCard project={mockProject} />);

      const card = screen.getByRole('button');
      card.focus();
      await user.keyboard('{Enter}');

      expect(mockPush).toHaveBeenCalledWith('/projects/proj-123');
    });

    it('navigates on keyboard Space', async () => {
      const user = userEvent.setup();
      render(<ProjectCard project={mockProject} />);

      const card = screen.getByRole('button');
      card.focus();
      await user.keyboard(' ');

      expect(mockPush).toHaveBeenCalledWith('/projects/proj-123');
    });
  });

  describe('with different project data', () => {
    it('renders long project names with truncation', () => {
      const longNameProject: Project = {
        ...mockProject,
        name: 'This is a very long project name that should be truncated',
      };

      render(<ProjectCard project={longNameProject} />);

      expect(
        screen.getByText('This is a very long project name that should be truncated')
      ).toBeInTheDocument();
    });

    it('renders long URLs with truncation', () => {
      const longUrlProject: Project = {
        ...mockProject,
        site_url: 'https://very-long-subdomain.example.com/path/to/resource',
      };

      render(<ProjectCard project={longUrlProject} />);

      expect(
        screen.getByText('https://very-long-subdomain.example.com/path/to/resource')
      ).toBeInTheDocument();
    });
  });
});
