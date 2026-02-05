import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AlternativeKeywordDropdown } from '../onboarding/AlternativeKeywordDropdown';
import type { AlternativeKeyword } from '@/lib/api';

// ============================================================================
// Mock hooks
// ============================================================================
const mockUpdatePrimaryKeyword = {
  mutateAsync: vi.fn(),
  isPending: false,
};

vi.mock('@/hooks/useKeywordMutations', () => ({
  useUpdatePrimaryKeyword: () => mockUpdatePrimaryKeyword,
}));

// ============================================================================
// Mock data
// ============================================================================
const mockProjectId = 'project-abc';
const mockPageId = 'page-123';
const mockPrimaryKeyword = 'running shoes';
const mockPrimaryVolume = 12500;
const mockPrimaryScore = 52.3;

// Alternatives with full data
const mockAlternatives: AlternativeKeyword[] = [
  { keyword: 'best running shoes', volume: 8000, composite_score: 45.2 },
  { keyword: 'trail running shoes', volume: 5000, composite_score: 42.1 },
  { keyword: 'running shoes for men', volume: 6000, composite_score: 40.5 },
  { keyword: 'cheap running shoes', volume: 4000, composite_score: 35.0 },
];

const mockAnchorRect: DOMRect = {
  top: 100,
  bottom: 130,
  left: 200,
  right: 400,
  width: 200,
  height: 30,
  x: 200,
  y: 100,
  toJSON: () => ({}),
};

const defaultProps = {
  primaryKeyword: mockPrimaryKeyword,
  alternatives: mockAlternatives,
  primaryVolume: mockPrimaryVolume,
  primaryScore: mockPrimaryScore,
  projectId: mockProjectId,
  pageId: mockPageId,
  isOpen: true,
  onClose: vi.fn(),
  anchorRect: mockAnchorRect,
};

// ============================================================================
// Unit Tests: AlternativeKeywordDropdown
// ============================================================================
describe('AlternativeKeywordDropdown', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUpdatePrimaryKeyword.isPending = false;
    mockUpdatePrimaryKeyword.mutateAsync.mockResolvedValue({});
  });

  // ============================================================================
  // Dropdown visibility tests
  // ============================================================================
  describe('dropdown visibility', () => {
    it('renders when isOpen is true', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      expect(screen.getByRole('listbox')).toBeInTheDocument();
    });

    it('does not render when isOpen is false', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} isOpen={false} />);

      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    });

    it('does not render when anchorRect is null', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} anchorRect={null} />);

      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    });
  });

  // ============================================================================
  // Primary keyword display tests
  // ============================================================================
  describe('primary keyword display', () => {
    it('displays current primary keyword at top', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      const primaryOption = screen.getByRole('option', { selected: true });
      expect(primaryOption).toHaveTextContent('running shoes');
    });

    it('displays primary keyword volume', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      expect(screen.getByText('12,500 vol')).toBeInTheDocument();
    });

    it('displays primary keyword score', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      expect(screen.getByText('52.3')).toBeInTheDocument();
    });

    it('shows checkmark icon for primary keyword', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      const primaryOption = screen.getByRole('option', { selected: true });
      const checkIcon = primaryOption.querySelector('svg');
      expect(checkIcon).toBeInTheDocument();
    });

    it('does not show volume when primaryVolume is null', () => {
      render(
        <AlternativeKeywordDropdown
          {...defaultProps}
          primaryVolume={null}
          alternatives={[]}
        />
      );

      // Primary keyword should still be there
      expect(screen.getByText('running shoes')).toBeInTheDocument();
      // Primary keyword section should not have volume text
      const primarySection = screen.getByRole('option', { selected: true });
      expect(primarySection).not.toHaveTextContent('vol');
    });
  });

  // ============================================================================
  // Alternatives listing tests
  // ============================================================================
  describe('alternatives listing', () => {
    it('lists all alternative keywords', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      expect(screen.getByText('best running shoes')).toBeInTheDocument();
      expect(screen.getByText('trail running shoes')).toBeInTheDocument();
      expect(screen.getByText('running shoes for men')).toBeInTheDocument();
      expect(screen.getByText('cheap running shoes')).toBeInTheDocument();
    });

    it('displays volume for each alternative', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      expect(screen.getByText('8,000 vol')).toBeInTheDocument();
      expect(screen.getByText('5,000 vol')).toBeInTheDocument();
      expect(screen.getByText('6,000 vol')).toBeInTheDocument();
      expect(screen.getByText('4,000 vol')).toBeInTheDocument();
    });

    it('displays composite score for each alternative', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      expect(screen.getByText('45.2')).toBeInTheDocument();
      expect(screen.getByText('42.1')).toBeInTheDocument();
      expect(screen.getByText('40.5')).toBeInTheDocument();
      expect(screen.getByText('35.0')).toBeInTheDocument();
    });

    it('limits alternatives to 4 items', () => {
      const fiveAlternatives: AlternativeKeyword[] = [
        ...mockAlternatives,
        { keyword: 'fifth alternative', volume: 3000, composite_score: 30.0 },
      ];

      render(
        <AlternativeKeywordDropdown
          {...defaultProps}
          alternatives={fiveAlternatives}
        />
      );

      expect(screen.getByText('best running shoes')).toBeInTheDocument();
      expect(screen.getByText('cheap running shoes')).toBeInTheDocument();
      expect(screen.queryByText('fifth alternative')).not.toBeInTheDocument();
    });

    it('shows "No alternatives available" when alternatives is empty', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} alternatives={[]} />);

      expect(screen.getByText('No alternatives available')).toBeInTheDocument();
    });

    it('renders alternatives as interactive options', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      // Each keyword (primary + alternatives) should be an option
      const options = screen.getAllByRole('option');
      // 1 primary + 4 alternatives = 5 options
      expect(options.length).toBe(5);
    });
  });

  // ============================================================================
  // Selection behavior tests
  // ============================================================================
  describe('selecting alternative', () => {
    it('calls mutation when alternative is clicked', async () => {
      const user = userEvent.setup();
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      await user.click(screen.getByText('best running shoes'));

      expect(mockUpdatePrimaryKeyword.mutateAsync).toHaveBeenCalledWith({
        projectId: mockProjectId,
        pageId: mockPageId,
        keyword: 'best running shoes',
      });
    });

    it('calls onClose after successful selection', async () => {
      const user = userEvent.setup();
      const mockOnClose = vi.fn();
      render(<AlternativeKeywordDropdown {...defaultProps} onClose={mockOnClose} />);

      await user.click(screen.getByText('trail running shoes'));

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalled();
      });
    });

    it('does not call mutation when clicking primary keyword', async () => {
      const user = userEvent.setup();
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      // The primary keyword is not a button, it's just displayed
      const primaryOption = screen.getByRole('option', { selected: true });
      await user.click(primaryOption);

      expect(mockUpdatePrimaryKeyword.mutateAsync).not.toHaveBeenCalled();
    });

    it('shows loading spinner on selected alternative during mutation', async () => {
      const user = userEvent.setup();
      // Create a promise that we control when it resolves
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });
      mockUpdatePrimaryKeyword.mutateAsync.mockReturnValue(pendingPromise);

      const { rerender } = render(<AlternativeKeywordDropdown {...defaultProps} />);

      // Click the alternative - this will set selectedKeyword state
      await user.click(screen.getByText('best running shoes'));

      // Simulate pending state by setting isPending and re-rendering
      mockUpdatePrimaryKeyword.isPending = true;
      rerender(<AlternativeKeywordDropdown {...defaultProps} />);

      // The component tracks which keyword is being selected via selectedKeyword state
      // and shows spinner when isPending is true
      await waitFor(() => {
        const loadingSpinner = document.querySelector('.animate-spin');
        expect(loadingSpinner).toBeInTheDocument();
      });

      // Cleanup: resolve the promise
      resolvePromise!({});
    });

    it('disables other alternatives during mutation', () => {
      // Set isPending to true to simulate loading state
      mockUpdatePrimaryKeyword.isPending = true;

      render(<AlternativeKeywordDropdown {...defaultProps} />);

      // All options that are not the primary should be disabled when isPending is true
      const options = screen.getAllByRole('option');
      expect(options.length).toBe(5);

      // All alternative options (non-selected ones) should be disabled
      const nonSelectedOptions = options.filter(
        (opt) => opt.getAttribute('aria-selected') === 'false'
      );
      nonSelectedOptions.forEach((option) => {
        expect(option).toBeDisabled();
      });
    });

    it('does not close on mutation error', async () => {
      const user = userEvent.setup();
      const mockOnClose = vi.fn();
      mockUpdatePrimaryKeyword.mutateAsync.mockRejectedValue(new Error('API Error'));

      render(<AlternativeKeywordDropdown {...defaultProps} onClose={mockOnClose} />);

      await user.click(screen.getByText('best running shoes'));

      await waitFor(() => {
        expect(mockUpdatePrimaryKeyword.mutateAsync).toHaveBeenCalled();
      });

      // onClose should NOT have been called due to error
      expect(mockOnClose).not.toHaveBeenCalled();
    });
  });

  // ============================================================================
  // Close behavior tests
  // ============================================================================
  describe('close behavior', () => {
    it('calls onClose when Escape key is pressed', async () => {
      const user = userEvent.setup();
      const mockOnClose = vi.fn();
      render(<AlternativeKeywordDropdown {...defaultProps} onClose={mockOnClose} />);

      // Need to wait for the setTimeout(0) in the component
      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument();
      });

      await user.keyboard('{Escape}');

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalled();
      });
    });

    it('calls onClose when clicking outside dropdown', async () => {
      const user = userEvent.setup();
      const mockOnClose = vi.fn();
      render(
        <div>
          <div data-testid="outside">Outside</div>
          <AlternativeKeywordDropdown {...defaultProps} onClose={mockOnClose} />
        </div>
      );

      // Need to wait for the setTimeout(0) in the component
      await waitFor(() => {
        expect(screen.getByRole('listbox')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('outside'));

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalled();
      });
    });
  });

  // ============================================================================
  // Accessibility tests
  // ============================================================================
  describe('accessibility', () => {
    it('has role="listbox" on dropdown container', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      expect(screen.getByRole('listbox')).toBeInTheDocument();
    });

    it('has aria-label on dropdown', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      expect(screen.getByRole('listbox')).toHaveAttribute(
        'aria-label',
        'Select keyword'
      );
    });

    it('has role="option" on each keyword', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      const options = screen.getAllByRole('option');
      // 1 primary + 4 alternatives = 5 options
      expect(options.length).toBe(5);
    });

    it('has aria-selected="true" on primary keyword', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      const selectedOption = screen.getByRole('option', { selected: true });
      expect(selectedOption).toHaveAttribute('aria-selected', 'true');
    });

    it('has aria-selected="false" on alternatives', () => {
      render(<AlternativeKeywordDropdown {...defaultProps} />);

      const unselectedOptions = screen.getAllByRole('option', { selected: false });
      expect(unselectedOptions.length).toBe(4);
      unselectedOptions.forEach((option) => {
        expect(option).toHaveAttribute('aria-selected', 'false');
      });
    });
  });

  // ============================================================================
  // Edge cases
  // ============================================================================
  describe('edge cases', () => {
    it('handles alternative with null volume', () => {
      const alternativesWithNullVolume: AlternativeKeyword[] = [
        { keyword: 'keyword with no volume', volume: null, composite_score: 40.0 },
      ];

      render(
        <AlternativeKeywordDropdown
          {...defaultProps}
          alternatives={alternativesWithNullVolume}
        />
      );

      expect(screen.getByText('keyword with no volume')).toBeInTheDocument();
      // Should show score but not volume
      expect(screen.getByText('40.0')).toBeInTheDocument();
    });

    it('handles alternative with null composite_score', () => {
      const alternativesWithNullScore: AlternativeKeyword[] = [
        { keyword: 'keyword with no score', volume: 5000, composite_score: null },
      ];

      render(
        <AlternativeKeywordDropdown
          {...defaultProps}
          alternatives={alternativesWithNullScore}
        />
      );

      expect(screen.getByText('keyword with no score')).toBeInTheDocument();
      // Should show volume but not score
      expect(screen.getByText('5,000 vol')).toBeInTheDocument();
    });

    it('handles case-insensitive matching for primary keyword in alternatives', async () => {
      const user = userEvent.setup();
      const alternativesWithPrimary: AlternativeKeyword[] = [
        { keyword: 'Running Shoes', volume: 12500, composite_score: 50.0 }, // Same as primary but different case
        { keyword: 'other keyword', volume: 3000, composite_score: 30.0 },
      ];

      render(
        <AlternativeKeywordDropdown
          {...defaultProps}
          alternatives={alternativesWithPrimary}
        />
      );

      // Find all options
      const options = screen.getAllByRole('option');

      // Find the "Running Shoes" alternative option (not the primary which is a div)
      const runningShoeOption = options.find(
        (opt) =>
          opt.textContent?.includes('Running Shoes') &&
          opt.tagName.toLowerCase() === 'button'
      );

      expect(runningShoeOption).toBeDefined();

      // The matching keyword should be marked as selected since it matches primary
      expect(runningShoeOption).toHaveAttribute('aria-selected', 'true');

      // It should also be disabled
      expect(runningShoeOption).toBeDisabled();

      // Click on it anyway - should not call mutation
      await user.click(runningShoeOption!);
      expect(mockUpdatePrimaryKeyword.mutateAsync).not.toHaveBeenCalled();
    });

    it('handles long keyword text gracefully', () => {
      const alternativesWithLongKeyword: AlternativeKeyword[] = [
        {
          keyword: 'this is a very long keyword that should be truncated properly in the UI',
          volume: 1000,
          composite_score: 25.0,
        },
      ];

      render(
        <AlternativeKeywordDropdown
          {...defaultProps}
          alternatives={alternativesWithLongKeyword}
        />
      );

      expect(
        screen.getByText(
          'this is a very long keyword that should be truncated properly in the UI'
        )
      ).toBeInTheDocument();
    });
  });
});
