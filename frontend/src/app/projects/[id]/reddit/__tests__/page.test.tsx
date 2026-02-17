import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ProjectRedditConfigPage from '../page';

// ============================================================================
// Mock Next.js navigation
// ============================================================================
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'test-project-123' }),
}));

// ============================================================================
// Mock hooks
// ============================================================================
const mockUseProject = vi.fn();
vi.mock('@/hooks/use-projects', () => ({
  useProject: (...args: unknown[]) => mockUseProject(...args),
}));

const mockUseRedditConfig = vi.fn();
const mockUpsertMutate = vi.fn();
const mockUseUpsertRedditConfig = vi.fn();
vi.mock('@/hooks/useReddit', () => ({
  useRedditConfig: (...args: unknown[]) => mockUseRedditConfig(...args),
  useUpsertRedditConfig: (...args: unknown[]) => mockUseUpsertRedditConfig(...args),
}));

// ============================================================================
// Mock data
// ============================================================================
const mockProject = {
  id: 'test-project-123',
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

const mockExistingConfig = {
  id: 'config-1',
  project_id: 'test-project-123',
  search_keywords: ['running shoes', 'marathon training'],
  target_subreddits: ['running', 'fitness'],
  banned_subreddits: ['spam'],
  competitors: ['competitor.com'],
  comment_instructions: 'Be helpful and authentic',
  niche_tags: ['fitness'],
  discovery_settings: { time_range: '7d', max_posts: 50 },
  is_active: true,
  created_at: '2026-01-20T00:00:00Z',
  updated_at: '2026-02-10T00:00:00Z',
};

// ============================================================================
// Default mock values
// ============================================================================
const defaultMockProject = () => ({
  data: mockProject,
  isLoading: false,
  error: null,
});

const defaultMockRedditConfig = () => ({
  data: mockExistingConfig,
  isLoading: false,
  error: null,
});

const defaultMockUpsert = () => ({
  mutate: mockUpsertMutate,
  isPending: false,
});

// ============================================================================
// Tests
// ============================================================================
describe('ProjectRedditConfigPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseProject.mockReturnValue(defaultMockProject());
    mockUseRedditConfig.mockReturnValue(defaultMockRedditConfig());
    mockUseUpsertRedditConfig.mockReturnValue(defaultMockUpsert());
  });

  // ============================================================================
  // Form rendering
  // ============================================================================
  describe('form rendering', () => {
    it('renders the page title', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('Reddit Settings')).toBeInTheDocument();
    });

    it('renders project name subtitle', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });

    it('renders all tag input fields', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.getByLabelText('Search Keywords')).toBeInTheDocument();
      expect(screen.getByLabelText('Target Subreddits')).toBeInTheDocument();
      expect(screen.getByLabelText('Banned Subreddits')).toBeInTheDocument();
      expect(screen.getByLabelText('Competitors')).toBeInTheDocument();
      expect(screen.getByLabelText('Niche Tags')).toBeInTheDocument();
    });

    it('renders comment instructions textarea', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.getByLabelText('Comment Instructions')).toBeInTheDocument();
    });

    it('renders discovery settings (Time Range and Max Posts)', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.getByLabelText('Time Range')).toBeInTheDocument();
      expect(screen.getByLabelText('Max Posts')).toBeInTheDocument();
    });

    it('renders the active/inactive toggle', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.getByRole('switch')).toBeInTheDocument();
      expect(screen.getByText('Active')).toBeInTheDocument();
    });

    it('renders Save Settings button', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('Save Settings')).toBeInTheDocument();
    });

    it('renders back link to project', () => {
      render(<ProjectRedditConfigPage />);

      const backLink = screen.getByText(/Back to Test Project/);
      expect(backLink).toBeInTheDocument();
      expect(backLink.closest('a')).toHaveAttribute('href', '/projects/test-project-123');
    });
  });

  // ============================================================================
  // Loading existing config
  // ============================================================================
  describe('loading existing config', () => {
    it('displays existing search keywords as tags', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('running shoes')).toBeInTheDocument();
      expect(screen.getByText('marathon training')).toBeInTheDocument();
    });

    it('displays existing target subreddits with r/ prefix', () => {
      render(<ProjectRedditConfigPage />);

      // The prefix is rendered alongside the tag text
      expect(screen.getByText((_, el) => el?.textContent === 'r/running')).toBeInTheDocument();
      expect(screen.getByText((_, el) => el?.textContent === 'r/fitness')).toBeInTheDocument();
    });

    it('displays existing comment instructions', () => {
      render(<ProjectRedditConfigPage />);

      const textarea = screen.getByLabelText('Comment Instructions');
      expect(textarea).toHaveValue('Be helpful and authentic');
    });

    it('displays existing toggle state', () => {
      render(<ProjectRedditConfigPage />);

      const toggle = screen.getByRole('switch');
      expect(toggle).toHaveAttribute('aria-checked', 'true');
    });
  });

  // ============================================================================
  // Save calls API
  // ============================================================================
  describe('save functionality', () => {
    it('calls upsert mutation when Save Settings is clicked', async () => {
      const user = userEvent.setup();
      render(<ProjectRedditConfigPage />);

      await user.click(screen.getByText('Save Settings'));

      expect(mockUpsertMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          search_keywords: ['running shoes', 'marathon training'],
          target_subreddits: ['running', 'fitness'],
          is_active: true,
        }),
        expect.any(Object),
      );
    });

    it('shows "Saving..." text when mutation is pending', () => {
      mockUseUpsertRedditConfig.mockReturnValue({
        mutate: mockUpsertMutate,
        isPending: true,
      });

      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('Saving...')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Empty config (404)
  // ============================================================================
  describe('no existing config', () => {
    it('renders form with defaults when config returns 404', () => {
      mockUseRedditConfig.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: { status: 404, message: 'Not found' },
      });

      render(<ProjectRedditConfigPage />);

      // Form should render with empty defaults
      expect(screen.getByText('Reddit Settings')).toBeInTheDocument();
      expect(screen.getByText('Save Settings')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Loading state
  // ============================================================================
  describe('loading state', () => {
    it('renders loading skeleton when project is loading', () => {
      mockUseProject.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });

      render(<ProjectRedditConfigPage />);

      const skeleton = document.querySelector('.animate-pulse');
      expect(skeleton).toBeInTheDocument();
    });

    it('renders loading skeleton when config is loading', () => {
      mockUseRedditConfig.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });

      render(<ProjectRedditConfigPage />);

      const skeleton = document.querySelector('.animate-pulse');
      expect(skeleton).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Project not found
  // ============================================================================
  describe('project not found', () => {
    it('shows error state when project errors', () => {
      mockUseProject.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Not found'),
      });

      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('Project Not Found')).toBeInTheDocument();
    });
  });
});
