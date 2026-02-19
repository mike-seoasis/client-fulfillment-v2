import { render, screen, within } from '@testing-library/react';
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
const mockTriggerMutate = vi.fn();
const mockUseTriggerDiscovery = vi.fn();
const mockUseDiscoveryStatus = vi.fn();
const mockUseRedditPosts = vi.fn();
const mockUpdatePostMutate = vi.fn();
const mockUseUpdatePostStatus = vi.fn();
vi.mock('@/hooks/useReddit', () => ({
  useRedditConfig: (...args: unknown[]) => mockUseRedditConfig(...args),
  useUpsertRedditConfig: (...args: unknown[]) => mockUseUpsertRedditConfig(...args),
  useTriggerDiscovery: (...args: unknown[]) => mockUseTriggerDiscovery(...args),
  useDiscoveryStatus: (...args: unknown[]) => mockUseDiscoveryStatus(...args),
  useRedditPosts: (...args: unknown[]) => mockUseRedditPosts(...args),
  useUpdatePostStatus: (...args: unknown[]) => mockUseUpdatePostStatus(...args),
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
// Mock post data for discovery tests
// ============================================================================
const mockPosts = [
  {
    id: 'post-1',
    project_id: 'test-project-123',
    reddit_post_id: 't3_abc',
    subreddit: 'SkincareAddiction',
    title: 'Best moisturizer for dry skin?',
    url: 'https://reddit.com/r/SkincareAddiction/comments/abc/best_moisturizer/',
    snippet: 'Looking for recommendations',
    keyword: 'moisturizer',
    intent: 'research',
    intent_categories: ['research', 'question'],
    relevance_score: 0.8,
    matched_keywords: ['research:recommend', 'question:?'],
    ai_evaluation: { score: 8, reasoning: 'Good fit' },
    filter_status: 'relevant',
    serp_position: 1,
    discovered_at: '2026-02-16T00:00:00Z',
    created_at: '2026-02-16T00:00:00Z',
    updated_at: '2026-02-16T00:00:00Z',
  },
  {
    id: 'post-2',
    project_id: 'test-project-123',
    reddit_post_id: 't3_def',
    subreddit: 'beauty',
    title: 'Struggling with sensitive skin',
    url: 'https://reddit.com/r/beauty/comments/def/struggling/',
    snippet: 'My skin is terrible and I am frustrated',
    keyword: 'sensitive skin',
    intent: 'pain_point',
    intent_categories: ['pain_point'],
    relevance_score: 0.5,
    matched_keywords: ['pain_point:struggling'],
    ai_evaluation: { score: 5, reasoning: 'Moderate fit' },
    filter_status: 'pending',
    serp_position: 3,
    discovered_at: '2026-02-16T00:00:00Z',
    created_at: '2026-02-16T00:00:00Z',
    updated_at: '2026-02-16T00:00:00Z',
  },
  {
    id: 'post-3',
    project_id: 'test-project-123',
    reddit_post_id: 't3_ghi',
    subreddit: 'SkincareAddiction',
    title: 'CeraVe vs Cetaphil review',
    url: 'https://reddit.com/r/SkincareAddiction/comments/ghi/cerave_vs/',
    snippet: 'Comparing brands for oily skin',
    keyword: 'cerave',
    intent: 'competitor',
    intent_categories: ['competitor', 'research'],
    relevance_score: 0.2,
    matched_keywords: ['competitor:CeraVe'],
    ai_evaluation: { score: 2, reasoning: 'Low relevance' },
    filter_status: 'low_relevance',
    serp_position: 5,
    discovered_at: '2026-02-16T00:00:00Z',
    created_at: '2026-02-16T00:00:00Z',
    updated_at: '2026-02-16T00:00:00Z',
  },
];

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

const defaultMockTriggerDiscovery = () => ({
  mutate: mockTriggerMutate,
  isPending: false,
});

const defaultMockDiscoveryStatus = () => ({
  data: { status: 'idle', total_keywords: 0, keywords_searched: 0, total_posts_found: 0, posts_scored: 0, posts_stored: 0, error: null },
  isLoading: false,
  error: null,
});

const defaultMockPosts = () => ({
  data: mockPosts,
  isLoading: false,
  error: null,
});

const defaultMockUpdatePost = () => ({
  mutate: mockUpdatePostMutate,
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
    mockUseTriggerDiscovery.mockReturnValue(defaultMockTriggerDiscovery());
    mockUseDiscoveryStatus.mockReturnValue(defaultMockDiscoveryStatus());
    mockUseRedditPosts.mockReturnValue(defaultMockPosts());
    mockUseUpdatePostStatus.mockReturnValue(defaultMockUpdatePost());
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

  // ============================================================================
  // Discovery trigger button
  // ============================================================================
  describe('discovery trigger button', () => {
    it('renders Discover Posts button', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('Discover Posts')).toBeInTheDocument();
    });

    it('button is enabled when config exists with keywords', () => {
      render(<ProjectRedditConfigPage />);

      const buttons = screen.getAllByText('Discover Posts');
      // The main button (not the empty state one)
      const mainButton = buttons[0].closest('button');
      expect(mainButton).not.toBeDisabled();
    });

    it('button is disabled when no config exists', () => {
      mockUseRedditConfig.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: null,
      });
      mockUseRedditPosts.mockReturnValue({ data: [], isLoading: false, error: null });

      render(<ProjectRedditConfigPage />);

      const buttons = screen.getAllByText('Discover Posts');
      const mainButton = buttons[0].closest('button');
      expect(mainButton).toBeDisabled();
    });

    it('button is disabled when config has no keywords', () => {
      mockUseRedditConfig.mockReturnValue({
        data: { ...mockExistingConfig, search_keywords: [] },
        isLoading: false,
        error: null,
      });

      render(<ProjectRedditConfigPage />);

      const buttons = screen.getAllByText('Discover Posts');
      const mainButton = buttons[0].closest('button');
      expect(mainButton).toBeDisabled();
    });

    it('shows Starting... text when trigger mutation is pending', () => {
      mockUseTriggerDiscovery.mockReturnValue({
        mutate: mockTriggerMutate,
        isPending: true,
      });

      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('Starting...')).toBeInTheDocument();
    });

    it('button is disabled during active discovery', () => {
      mockUseDiscoveryStatus.mockReturnValue({
        data: { status: 'searching', total_keywords: 3, keywords_searched: 1, total_posts_found: 5, posts_scored: 0, posts_stored: 0, error: null },
        isLoading: false,
        error: null,
      });

      render(<ProjectRedditConfigPage />);

      const buttons = screen.getAllByText('Discover Posts');
      const mainButton = buttons[0].closest('button');
      expect(mainButton).toBeDisabled();
    });

    it('calls trigger mutation when clicked', async () => {
      const user = userEvent.setup();
      render(<ProjectRedditConfigPage />);

      const buttons = screen.getAllByText('Discover Posts');
      await user.click(buttons[0]);

      expect(mockTriggerMutate).toHaveBeenCalled();
    });
  });

  // ============================================================================
  // Discovery progress indicator
  // ============================================================================
  describe('discovery progress', () => {
    it('shows searching progress when discovery is searching', () => {
      mockUseDiscoveryStatus.mockReturnValue({
        data: {
          status: 'searching',
          total_keywords: 5,
          keywords_searched: 2,
          total_posts_found: 10,
          posts_scored: 0,
          posts_stored: 0,
          error: null,
        },
        isLoading: false,
        error: null,
      });

      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('Searching keywords...')).toBeInTheDocument();
      expect(screen.getByText(/Keywords: 2\/5/)).toBeInTheDocument();
    });

    it('shows scoring progress when discovery is scoring', () => {
      mockUseDiscoveryStatus.mockReturnValue({
        data: {
          status: 'scoring',
          total_keywords: 5,
          keywords_searched: 5,
          total_posts_found: 20,
          posts_scored: 8,
          posts_stored: 0,
          error: null,
        },
        isLoading: false,
        error: null,
      });

      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('Scoring posts with AI...')).toBeInTheDocument();
      expect(screen.getByText(/Scored: 8/)).toBeInTheDocument();
    });

    it('shows completion summary when discovery is complete', () => {
      mockUseDiscoveryStatus.mockReturnValue({
        data: {
          status: 'complete',
          total_keywords: 5,
          keywords_searched: 5,
          total_posts_found: 20,
          posts_scored: 15,
          posts_stored: 15,
          error: null,
        },
        isLoading: false,
        error: null,
      });

      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('Discovery complete')).toBeInTheDocument();
      expect(screen.getByText(/Stored: 15/)).toBeInTheDocument();
    });

    it('shows error when discovery fails', () => {
      mockUseDiscoveryStatus.mockReturnValue({
        data: {
          status: 'failed',
          total_keywords: 5,
          keywords_searched: 3,
          total_posts_found: 10,
          posts_scored: 0,
          posts_stored: 0,
          error: 'SerpAPI rate limit exceeded',
        },
        isLoading: false,
        error: null,
      });

      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('Discovery failed')).toBeInTheDocument();
      expect(screen.getByText('SerpAPI rate limit exceeded')).toBeInTheDocument();
    });

    it('does not show progress indicator when status is idle', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.queryByText('Searching keywords...')).not.toBeInTheDocument();
      expect(screen.queryByText('Discovery complete')).not.toBeInTheDocument();
    });
  });

  // ============================================================================
  // Posts table rendering
  // ============================================================================
  describe('posts table', () => {
    it('renders table headers', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('Subreddit')).toBeInTheDocument();
      expect(screen.getByText('Title')).toBeInTheDocument();
      expect(screen.getByText('Intent')).toBeInTheDocument();
      expect(screen.getByText('Score')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
      expect(screen.getByText('Discovered')).toBeInTheDocument();
      expect(screen.getByText('Actions')).toBeInTheDocument();
    });

    it('renders post rows with subreddit names', () => {
      render(<ProjectRedditConfigPage />);

      // Two posts are from SkincareAddiction, one from beauty
      // The text nodes may be split across child elements, so use a custom matcher
      const skincareMentions = screen.getAllByText((_, el) => el?.textContent === 'r/SkincareAddiction');
      expect(skincareMentions.length).toBeGreaterThanOrEqual(2);
      const beautyMentions = screen.getAllByText((_, el) => el?.textContent === 'r/beauty');
      expect(beautyMentions.length).toBeGreaterThanOrEqual(1);
    });

    it('renders post titles as links to Reddit', () => {
      render(<ProjectRedditConfigPage />);

      const link = screen.getByText('Best moisturizer for dry skin?').closest('a');
      expect(link).toHaveAttribute('href', 'https://reddit.com/r/SkincareAddiction/comments/abc/best_moisturizer/');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('renders intent badges for posts', () => {
      render(<ProjectRedditConfigPage />);

      // Intent labels appear both as badges in the table and as options
      // in the filter dropdown, so use getAllByText
      const researchBadges = screen.getAllByText('Research');
      expect(researchBadges.length).toBeGreaterThanOrEqual(1);
      const painPointBadges = screen.getAllByText('Pain Point');
      expect(painPointBadges.length).toBeGreaterThanOrEqual(1);
      const competitorBadges = screen.getAllByText('Competitor');
      expect(competitorBadges.length).toBeGreaterThanOrEqual(1);
    });

    it('renders relevance scores with correct values', () => {
      render(<ProjectRedditConfigPage />);

      // Scores are displayed as X/10
      expect(screen.getByText('8/10')).toBeInTheDocument();
      expect(screen.getByText('5/10')).toBeInTheDocument();
      expect(screen.getByText('2/10')).toBeInTheDocument();
    });

    it('renders filter status badges', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('relevant')).toBeInTheDocument();
      expect(screen.getByText('pending')).toBeInTheDocument();
      expect(screen.getByText('Low Relevance')).toBeInTheDocument();
    });

    it('shows empty state when no posts', () => {
      mockUseRedditPosts.mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      });

      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('No posts discovered yet')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Filter tabs
  // ============================================================================
  describe('filter tabs', () => {
    it('renders status filter tabs', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('All')).toBeInTheDocument();
      expect(screen.getByText('Relevant')).toBeInTheDocument();
      expect(screen.getByText('Irrelevant')).toBeInTheDocument();
      expect(screen.getByText('Pending')).toBeInTheDocument();
    });

    it('renders intent filter dropdown', () => {
      render(<ProjectRedditConfigPage />);

      expect(screen.getByText('All Intents')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Approve / Reject actions
  // ============================================================================
  describe('approve and reject actions', () => {
    it('renders approve buttons for each post', () => {
      render(<ProjectRedditConfigPage />);

      const approveButtons = screen.getAllByLabelText('Approve post');
      expect(approveButtons.length).toBe(3);
    });

    it('renders reject buttons for each post', () => {
      render(<ProjectRedditConfigPage />);

      const rejectButtons = screen.getAllByLabelText('Reject post');
      expect(rejectButtons.length).toBe(3);
    });

    it('approve button is disabled for already-relevant posts', () => {
      render(<ProjectRedditConfigPage />);

      const approveButtons = screen.getAllByLabelText('Approve post');
      // First post (post-1) has filter_status='relevant'
      expect(approveButtons[0]).toBeDisabled();
      // Second post (post-2) has filter_status='pending' -- should NOT be disabled
      expect(approveButtons[1]).not.toBeDisabled();
    });

    it('reject button is disabled for already-skipped posts', () => {
      render(<ProjectRedditConfigPage />);

      const rejectButtons = screen.getAllByLabelText('Skip post');
      // Third post (post-3) has filter_status='low_relevance' -- skip should NOT be disabled
      expect(rejectButtons[2]).not.toBeDisabled();
      // First post (post-1) has filter_status='relevant' -- skip should NOT be disabled
      expect(rejectButtons[0]).not.toBeDisabled();
    });

    it('clicking approve calls updatePostStatus mutation', async () => {
      const user = userEvent.setup();
      render(<ProjectRedditConfigPage />);

      const approveButtons = screen.getAllByLabelText('Approve post');
      // Click approve on second post (pending status)
      await user.click(approveButtons[1]);

      expect(mockUpdatePostMutate).toHaveBeenCalledWith({
        postId: 'post-2',
        data: { filter_status: 'relevant' },
      });
    });

    it('clicking reject calls updatePostStatus mutation', async () => {
      const user = userEvent.setup();
      render(<ProjectRedditConfigPage />);

      const rejectButtons = screen.getAllByLabelText('Skip post');
      // Click skip on second post (pending status)
      await user.click(rejectButtons[1]);

      expect(mockUpdatePostMutate).toHaveBeenCalledWith({
        postId: 'post-2',
        data: { filter_status: 'skipped' },
      });
    });
  });
});
