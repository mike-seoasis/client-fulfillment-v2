import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import RedditAccountsPage from '../page';
import type { RedditAccount } from '@/lib/api';

// ============================================================================
// Mock hooks
// ============================================================================
const mockUseRedditAccounts = vi.fn();
const mockCreateMutate = vi.fn();
const mockUseCreateRedditAccount = vi.fn();
const mockDeleteMutate = vi.fn();
const mockUseDeleteRedditAccount = vi.fn();

vi.mock('@/hooks/useReddit', () => ({
  useRedditAccounts: (...args: unknown[]) => mockUseRedditAccounts(...args),
  useCreateRedditAccount: () => mockUseCreateRedditAccount(),
  useDeleteRedditAccount: () => mockUseDeleteRedditAccount(),
}));

// ============================================================================
// Mock data
// ============================================================================
const mockAccount: RedditAccount = {
  id: 'acc-1',
  username: 'test_user_42',
  status: 'active',
  warmup_stage: 'operational',
  niche_tags: ['fitness', 'nutrition'],
  karma_post: 1200,
  karma_comment: 3400,
  account_age_days: 365,
  cooldown_until: null,
  last_used_at: '2026-02-15T10:00:00Z',
  notes: null,
  extra_metadata: null,
  created_at: '2025-06-01T00:00:00Z',
  updated_at: '2026-02-15T10:00:00Z',
};

const mockAccount2: RedditAccount = {
  id: 'acc-2',
  username: 'health_guru',
  status: 'warming_up',
  warmup_stage: 'light_engagement',
  niche_tags: ['health'],
  karma_post: 50,
  karma_comment: 120,
  account_age_days: 30,
  cooldown_until: null,
  last_used_at: null,
  notes: 'New account',
  extra_metadata: null,
  created_at: '2026-01-15T00:00:00Z',
  updated_at: '2026-02-10T00:00:00Z',
};

// ============================================================================
// Default mock values
// ============================================================================
const defaultAccounts = () => ({
  data: [mockAccount, mockAccount2],
  isLoading: false,
  error: null,
});

const defaultCreateAccount = () => ({
  mutate: mockCreateMutate,
  isPending: false,
});

const defaultDeleteAccount = () => ({
  mutate: mockDeleteMutate,
  isPending: false,
});

// ============================================================================
// Tests
// ============================================================================
describe('RedditAccountsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseRedditAccounts.mockReturnValue(defaultAccounts());
    mockUseCreateRedditAccount.mockReturnValue(defaultCreateAccount());
    mockUseDeleteRedditAccount.mockReturnValue(defaultDeleteAccount());
  });

  // ============================================================================
  // Table rendering
  // ============================================================================
  describe('table rendering', () => {
    it('renders the accounts table with column headers', () => {
      render(<RedditAccountsPage />);

      const table = screen.getByRole('table');
      const headers = within(table).getAllByRole('columnheader');
      const headerTexts = headers.map((h) => h.textContent?.trim());

      expect(headerTexts).toContain('Username');
      expect(headerTexts).toContain('Status');
      expect(headerTexts).toContain('Warmup Stage');
      expect(headerTexts).toContain('Niche Tags');
      expect(headerTexts).toContain('Karma');
      expect(headerTexts).toContain('Cooldown');
      expect(headerTexts).toContain('Last Used');
    });

    it('renders account usernames in the table', () => {
      render(<RedditAccountsPage />);

      expect(screen.getByText('test_user_42')).toBeInTheDocument();
      expect(screen.getByText('health_guru')).toBeInTheDocument();
    });

    it('renders status badges in the table', () => {
      render(<RedditAccountsPage />);

      const table = screen.getByRole('table');
      // Status badges are inside the table rows
      expect(within(table).getByText('Active')).toBeInTheDocument();
      expect(within(table).getByText('Warming Up')).toBeInTheDocument();
    });

    it('renders warmup stage labels in the table', () => {
      render(<RedditAccountsPage />);

      const table = screen.getByRole('table');
      expect(within(table).getByText('Operational')).toBeInTheDocument();
      expect(within(table).getByText('Light Engagement')).toBeInTheDocument();
    });

    it('renders niche tags as chips in the table', () => {
      render(<RedditAccountsPage />);

      const table = screen.getByRole('table');
      expect(within(table).getByText('fitness')).toBeInTheDocument();
      expect(within(table).getByText('nutrition')).toBeInTheDocument();
      expect(within(table).getByText('health')).toBeInTheDocument();
    });

    it('renders karma values', () => {
      render(<RedditAccountsPage />);

      // karma_post / karma_comment format
      expect(screen.getByText('1200 / 3400')).toBeInTheDocument();
      expect(screen.getByText('50 / 120')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Filter controls
  // ============================================================================
  describe('filter controls', () => {
    it('renders three filter dropdowns', () => {
      render(<RedditAccountsPage />);

      // The filter selects have default option labels
      const selects = screen.getAllByRole('combobox');
      expect(selects.length).toBe(3);
    });

    it('shows "All Niches" option in the niche filter', () => {
      render(<RedditAccountsPage />);

      const selects = screen.getAllByRole('combobox');
      // First select is the niche filter
      expect(within(selects[0]).getByText('All Niches')).toBeInTheDocument();
    });

    it('shows "All Stages" option in the warmup filter', () => {
      render(<RedditAccountsPage />);

      const selects = screen.getAllByRole('combobox');
      expect(within(selects[1]).getByText('All Stages')).toBeInTheDocument();
    });

    it('shows "All Statuses" option in the status filter', () => {
      render(<RedditAccountsPage />);

      const selects = screen.getAllByRole('combobox');
      expect(within(selects[2]).getByText('All Statuses')).toBeInTheDocument();
    });

    it('shows "Clear filters" button when a filter is applied', async () => {
      const user = userEvent.setup();
      render(<RedditAccountsPage />);

      // No clear filters button initially
      expect(screen.queryByText('Clear filters')).not.toBeInTheDocument();

      // Select a status filter
      const selects = screen.getAllByRole('combobox');
      await user.selectOptions(selects[2], 'active');

      expect(screen.getByText('Clear filters')).toBeInTheDocument();
    });

    it('calls useRedditAccounts with filter params when filter is selected', async () => {
      const user = userEvent.setup();
      render(<RedditAccountsPage />);

      const selects = screen.getAllByRole('combobox');
      await user.selectOptions(selects[2], 'active');

      // useRedditAccounts should have been called with filter params
      // It gets called multiple times - check the last calls include the filter
      const calls = mockUseRedditAccounts.mock.calls;
      const lastFilteredCall = calls.find(
        (call: unknown[]) => call[0] && typeof call[0] === 'object' && 'status' in call[0],
      );
      expect(lastFilteredCall).toBeTruthy();
    });
  });

  // ============================================================================
  // Add account modal
  // ============================================================================
  describe('add account modal', () => {
    it('opens modal when "+ Add Account" button is clicked', async () => {
      const user = userEvent.setup();
      render(<RedditAccountsPage />);

      // Modal title should not be visible initially
      expect(screen.queryByText('Add Reddit Account')).not.toBeInTheDocument();

      // Click the add button
      await user.click(screen.getByText('+ Add Account'));

      // Modal should now be visible
      expect(screen.getByText('Add Reddit Account')).toBeInTheDocument();
    });

    it('renders modal form fields', async () => {
      const user = userEvent.setup();
      render(<RedditAccountsPage />);

      await user.click(screen.getByText('+ Add Account'));

      expect(screen.getByLabelText('Username')).toBeInTheDocument();
      expect(screen.getByLabelText('Niche Tags')).toBeInTheDocument();
      expect(screen.getByLabelText('Notes')).toBeInTheDocument();
    });

    it('closes modal when Cancel is clicked', async () => {
      const user = userEvent.setup();
      render(<RedditAccountsPage />);

      await user.click(screen.getByText('+ Add Account'));
      expect(screen.getByText('Add Reddit Account')).toBeInTheDocument();

      await user.click(screen.getByText('Cancel'));

      expect(screen.queryByText('Add Reddit Account')).not.toBeInTheDocument();
    });

    it('shows Add Account submit button in modal', async () => {
      const user = userEvent.setup();
      render(<RedditAccountsPage />);

      await user.click(screen.getByText('+ Add Account'));

      // The submit button inside the modal (different from the header button)
      const submitButton = screen.getByRole('button', { name: 'Add Account' });
      expect(submitButton).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Delete confirmation
  // ============================================================================
  describe('delete confirmation', () => {
    it('renders Delete button for each account row', () => {
      render(<RedditAccountsPage />);

      const deleteButtons = screen.getAllByRole('button', { name: 'Delete' });
      expect(deleteButtons.length).toBe(2);
    });

    it('shows "Confirm?" on first click of Delete', async () => {
      const user = userEvent.setup();
      render(<RedditAccountsPage />);

      const deleteButtons = screen.getAllByRole('button', { name: 'Delete' });
      await user.click(deleteButtons[0]);

      expect(screen.getByText('Confirm?')).toBeInTheDocument();
    });

    it('calls delete mutation on second click (confirm)', async () => {
      const user = userEvent.setup();
      render(<RedditAccountsPage />);

      const deleteButtons = screen.getAllByRole('button', { name: 'Delete' });
      // First click — enters confirm state
      await user.click(deleteButtons[0]);
      // Second click — confirms
      const confirmButton = screen.getByText('Confirm?');
      await user.click(confirmButton);

      expect(mockDeleteMutate).toHaveBeenCalledWith('acc-1', expect.any(Object));
    });
  });

  // ============================================================================
  // Empty state
  // ============================================================================
  describe('empty state', () => {
    it('renders empty state when no accounts exist', () => {
      mockUseRedditAccounts.mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      });

      render(<RedditAccountsPage />);

      expect(screen.getByText('No Reddit accounts yet')).toBeInTheDocument();
      expect(
        screen.getByText('Add your first Reddit account to start managing the shared pool.'),
      ).toBeInTheDocument();
    });

    it('renders empty filter results state when filters match nothing', async () => {
      const user = userEvent.setup();

      // First render: all accounts present for unfiltered, empty for filtered
      let callCount = 0;
      mockUseRedditAccounts.mockImplementation((params: unknown) => {
        callCount++;
        // Unfiltered calls (no params) return accounts
        if (!params || (typeof params === 'object' && Object.keys(params as object).length === 0)) {
          return { data: [mockAccount], isLoading: false, error: null };
        }
        // Filtered calls return empty
        return { data: [], isLoading: false, error: null };
      });

      render(<RedditAccountsPage />);

      // Apply a filter to get the empty filter state
      const selects = screen.getAllByRole('combobox');
      await user.selectOptions(selects[2], 'banned');

      expect(screen.getByText('No accounts match filters')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Loading state
  // ============================================================================
  describe('loading state', () => {
    it('renders loading skeleton when data is loading', () => {
      mockUseRedditAccounts.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });

      render(<RedditAccountsPage />);

      // Skeleton has animate-pulse
      const skeleton = document.querySelector('.animate-pulse');
      expect(skeleton).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Page header
  // ============================================================================
  describe('page header', () => {
    it('renders breadcrumb-style header', () => {
      render(<RedditAccountsPage />);

      expect(screen.getByText('Reddit')).toBeInTheDocument();
      expect(screen.getByText('Accounts')).toBeInTheDocument();
    });

    it('renders "+ Add Account" button in header', () => {
      render(<RedditAccountsPage />);

      expect(screen.getByText('+ Add Account')).toBeInTheDocument();
    });
  });
});
