import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  LabelEditDropdown,
  validateLabelCount,
  MIN_LABELS,
  MAX_LABELS,
} from '../LabelEditDropdown';

// ============================================================================
// Unit Tests: validateLabelCount function
// ============================================================================
describe('validateLabelCount', () => {
  it('returns null for valid count (2 labels)', () => {
    expect(validateLabelCount(2)).toBeNull();
  });

  it('returns null for valid count (3 labels)', () => {
    expect(validateLabelCount(3)).toBeNull();
  });

  it('returns null for valid count (5 labels)', () => {
    expect(validateLabelCount(5)).toBeNull();
  });

  it('returns error message for 0 labels', () => {
    expect(validateLabelCount(0)).toBe(`Select at least ${MIN_LABELS} labels`);
  });

  it('returns error message for 1 label', () => {
    expect(validateLabelCount(1)).toBe(`Select at least ${MIN_LABELS} labels`);
  });

  it('returns error message for 6 labels', () => {
    expect(validateLabelCount(6)).toBe(`Select at most ${MAX_LABELS} labels`);
  });

  it('returns error message for 10 labels', () => {
    expect(validateLabelCount(10)).toBe(`Select at most ${MAX_LABELS} labels`);
  });
});

// ============================================================================
// Constants Tests
// ============================================================================
describe('Label constants', () => {
  it('MIN_LABELS is 2', () => {
    expect(MIN_LABELS).toBe(2);
  });

  it('MAX_LABELS is 5', () => {
    expect(MAX_LABELS).toBe(5);
  });
});

// ============================================================================
// Mock data for tests
// ============================================================================
const mockTaxonomyLabels = [
  { name: 'trail-running', description: 'Trail running gear and shoes', examples: ['trail shoes', 'hydration'] },
  { name: 'hiking', description: 'Hiking equipment and apparel', examples: ['boots', 'backpacks'] },
  { name: 'camping', description: 'Camping gear and accessories', examples: ['tents', 'sleeping bags'] },
  { name: 'cycling', description: 'Cycling equipment and clothing', examples: ['bikes', 'helmets'] },
  { name: 'climbing', description: 'Rock climbing and bouldering', examples: ['harnesses', 'chalk'] },
  { name: 'water-sports', description: 'Water sports equipment', examples: ['kayaks', 'wetsuits'] },
  { name: 'winter-sports', description: 'Winter sports gear', examples: ['skis', 'snowboards'] },
];

// ============================================================================
// Component Tests: LabelEditDropdown rendering
// ============================================================================
describe('LabelEditDropdown', () => {
  const mockOnLabelsChange = vi.fn();
  const mockOnClose = vi.fn();
  const mockOnSave = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnSave.mockResolvedValue(undefined);
  });

  describe('rendering', () => {
    it('renders with "Edit Labels" header', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      expect(screen.getByText('Edit Labels')).toBeInTheDocument();
    });

    it('renders close button', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
    });

    it('renders Cancel and Save buttons', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
    });

    it('has role="dialog"', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  describe('taxonomy options display', () => {
    it('renders all taxonomy labels as checkboxes', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      mockTaxonomyLabels.forEach((label) => {
        expect(screen.getByText(label.name)).toBeInTheDocument();
      });
    });

    it('shows description for each taxonomy label', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      expect(screen.getByText('Trail running gear and shoes')).toBeInTheDocument();
      expect(screen.getByText('Hiking equipment and apparel')).toBeInTheDocument();
    });

    it('renders checkboxes with correct checked state', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');

      // Find the checkboxes by their parent element's text content
      const trailRunningCheckbox = checkboxes.find((cb) =>
        cb.closest('button')?.textContent?.includes('trail-running')
      );
      const hikingCheckbox = checkboxes.find((cb) =>
        cb.closest('button')?.textContent?.includes('hiking')
      );
      const campingCheckbox = checkboxes.find((cb) =>
        cb.closest('button')?.textContent?.includes('camping')
      );

      expect(trailRunningCheckbox).toHaveAttribute('aria-checked', 'true');
      expect(hikingCheckbox).toHaveAttribute('aria-checked', 'true');
      expect(campingCheckbox).toHaveAttribute('aria-checked', 'false');
    });

    it('handles empty taxonomy labels gracefully', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={[]}
          selectedLabels={[]}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      expect(screen.getByText('Edit Labels')).toBeInTheDocument();
      expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
    });
  });

  describe('selection count indicator', () => {
    it('shows "X of 2-5 labels selected" text', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking', 'camping']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      expect(screen.getByText(/3 of 2-5 labels selected/)).toBeInTheDocument();
    });

    it('shows validation error when count is below minimum', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      expect(screen.getByText(/Select at least 2 labels/)).toBeInTheDocument();
    });

    it('updates count when labels are toggled', async () => {
      const user = userEvent.setup();

      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      expect(screen.getByText(/2 of 2-5 labels selected/)).toBeInTheDocument();

      // Click to add a third label
      const campingOption = screen.getByText('camping').closest('button');
      await user.click(campingOption!);

      expect(screen.getByText(/3 of 2-5 labels selected/)).toBeInTheDocument();
    });
  });

  describe('checkbox interaction', () => {
    it('toggles label selection when clicked', async () => {
      const user = userEvent.setup();

      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      // Find and click the camping option
      const campingOption = screen.getByText('camping').closest('button');
      await user.click(campingOption!);

      // Verify it's now checked
      const checkboxes = screen.getAllByRole('checkbox');
      const campingCheckbox = checkboxes.find((cb) =>
        cb.closest('button')?.textContent?.includes('camping')
      );
      expect(campingCheckbox).toHaveAttribute('aria-checked', 'true');
    });

    it('deselects label when checked label is clicked', async () => {
      const user = userEvent.setup();

      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking', 'camping']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      // Find and click the camping option (which is selected)
      const campingOption = screen.getByText('camping').closest('button');
      await user.click(campingOption!);

      // Verify it's now unchecked
      const checkboxes = screen.getAllByRole('checkbox');
      const campingCheckbox = checkboxes.find((cb) =>
        cb.closest('button')?.textContent?.includes('camping')
      );
      expect(campingCheckbox).toHaveAttribute('aria-checked', 'false');
    });
  });

  describe('validation prevents <2 labels', () => {
    it('disables save button when 0 labels selected', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={[]}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      const saveButton = screen.getByRole('button', { name: 'Save' });
      expect(saveButton).toBeDisabled();
    });

    it('disables save button when 1 label selected', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      const saveButton = screen.getByRole('button', { name: 'Save' });
      expect(saveButton).toBeDisabled();
    });

    it('shows error message when deselecting below minimum', async () => {
      const user = userEvent.setup();

      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      // Deselect one label to go below minimum
      const hikingOption = screen.getByText('hiking').closest('button');
      await user.click(hikingOption!);

      expect(screen.getByText(/Select at least 2 labels/)).toBeInTheDocument();
    });
  });

  describe('validation prevents >5 labels', () => {
    it('shows error message when selection exceeds maximum', async () => {
      const user = userEvent.setup();

      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking', 'camping', 'cycling', 'climbing']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      // Add one more to exceed maximum
      const waterSportsOption = screen.getByText('water-sports').closest('button');
      await user.click(waterSportsOption!);

      expect(screen.getByText(/Select at most 5 labels/)).toBeInTheDocument();
    });

    it('disables save button when 6 labels selected', async () => {
      const user = userEvent.setup();

      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking', 'camping', 'cycling', 'climbing']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      // Add one more to exceed maximum
      const waterSportsOption = screen.getByText('water-sports').closest('button');
      await user.click(waterSportsOption!);

      const saveButton = screen.getByRole('button', { name: 'Save' });
      expect(saveButton).toBeDisabled();
    });
  });

  describe('save functionality', () => {
    it('enables save button with valid selection (2-5 labels) and changes', async () => {
      const user = userEvent.setup();

      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      // Add a label to make a change
      const campingOption = screen.getByText('camping').closest('button');
      await user.click(campingOption!);

      const saveButton = screen.getByRole('button', { name: 'Save' });
      expect(saveButton).not.toBeDisabled();
    });

    it('disables save button when no changes made', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      const saveButton = screen.getByRole('button', { name: 'Save' });
      expect(saveButton).toBeDisabled();
    });

    it('calls onSave with correct labels when save clicked', async () => {
      const user = userEvent.setup();

      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      // Add a label
      const campingOption = screen.getByText('camping').closest('button');
      await user.click(campingOption!);

      // Click save
      const saveButton = screen.getByRole('button', { name: 'Save' });
      await user.click(saveButton);

      expect(mockOnSave).toHaveBeenCalledTimes(1);
      // Should be called with array containing all three labels
      const savedLabels = mockOnSave.mock.calls[0][0] as string[];
      expect(savedLabels).toHaveLength(3);
      expect(savedLabels).toContain('trail-running');
      expect(savedLabels).toContain('hiking');
      expect(savedLabels).toContain('camping');
    });

    it('calls onLabelsChange when save clicked', async () => {
      const user = userEvent.setup();

      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      // Add a label
      const campingOption = screen.getByText('camping').closest('button');
      await user.click(campingOption!);

      // Click save
      const saveButton = screen.getByRole('button', { name: 'Save' });
      await user.click(saveButton);

      expect(mockOnLabelsChange).toHaveBeenCalledTimes(1);
    });

    it('shows "Saving..." text during save', async () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking', 'camping']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
          isSaving={true}
        />
      );

      expect(screen.getByRole('button', { name: 'Saving...' })).toBeInTheDocument();
    });

    it('disables save button during save', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking', 'camping']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
          isSaving={true}
        />
      );

      const saveButton = screen.getByRole('button', { name: 'Saving...' });
      expect(saveButton).toBeDisabled();
    });

    it('disables cancel button during save', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking', 'camping']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
          isSaving={true}
        />
      );

      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      expect(cancelButton).toBeDisabled();
    });
  });

  describe('close functionality', () => {
    it('calls onClose when close button clicked', async () => {
      const user = userEvent.setup();

      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      const closeButton = screen.getByRole('button', { name: 'Close' });
      await user.click(closeButton);

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when cancel button clicked', async () => {
      const user = userEvent.setup();

      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await user.click(cancelButton);

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when Escape key pressed', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      fireEvent.keyDown(document, { key: 'Escape' });

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when clicking outside dropdown', () => {
      render(
        <div>
          <div data-testid="outside">Outside element</div>
          <LabelEditDropdown
            taxonomyLabels={mockTaxonomyLabels}
            selectedLabels={['trail-running', 'hiking']}
            onLabelsChange={mockOnLabelsChange}
            onClose={mockOnClose}
            onSave={mockOnSave}
          />
        </div>
      );

      const outsideElement = screen.getByTestId('outside');
      fireEvent.mouseDown(outsideElement);

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('does not call onClose when clicking inside dropdown', async () => {
      const user = userEvent.setup();

      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      // Click on the dialog content
      const dialog = screen.getByRole('dialog');
      await user.click(dialog);

      expect(mockOnClose).not.toHaveBeenCalled();
    });
  });

  describe('label display in page context', () => {
    // These tests verify that label tags display correctly on pages
    // Testing the integration with PageListItem component patterns

    it('displays selected labels as visual checkboxes', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      // The selected labels should have visual checked state
      const checkboxes = screen.getAllByRole('checkbox');
      const selectedCheckboxes = checkboxes.filter((cb) =>
        cb.getAttribute('aria-checked') === 'true'
      );

      expect(selectedCheckboxes).toHaveLength(2);
    });

    it('highlights selected options with different background', async () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running', 'hiking']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      // Selected options should have palm-50 background class
      const trailRunningOption = screen.getByText('trail-running').closest('button');
      expect(trailRunningOption).toHaveClass('bg-palm-50');

      // Unselected options should not have the background
      const campingOption = screen.getByText('camping').closest('button');
      expect(campingOption).not.toHaveClass('bg-palm-50');
    });

    it('shows label name with bold text when selected', () => {
      render(
        <LabelEditDropdown
          taxonomyLabels={mockTaxonomyLabels}
          selectedLabels={['trail-running']}
          onLabelsChange={mockOnLabelsChange}
          onClose={mockOnClose}
          onSave={mockOnSave}
        />
      );

      const trailRunningText = screen.getByText('trail-running');
      expect(trailRunningText).toHaveClass('font-medium');
      expect(trailRunningText).toHaveClass('text-palm-700');
    });
  });
});

// ============================================================================
// Integration test: Label editing workflow
// ============================================================================
describe('Label editing workflow', () => {
  const mockOnLabelsChange = vi.fn();
  const mockOnClose = vi.fn();
  const mockOnSave = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnSave.mockResolvedValue(undefined);
  });

  it('complete workflow: view, edit, save labels', async () => {
    const user = userEvent.setup();

    render(
      <LabelEditDropdown
        taxonomyLabels={mockTaxonomyLabels}
        selectedLabels={['trail-running', 'hiking']}
        onLabelsChange={mockOnLabelsChange}
        onClose={mockOnClose}
        onSave={mockOnSave}
      />
    );

    // 1. Verify initial state shows current labels as selected
    expect(screen.getByText(/2 of 2-5 labels selected/)).toBeInTheDocument();

    // 2. Add a new label
    const campingOption = screen.getByText('camping').closest('button');
    await user.click(campingOption!);

    // 3. Verify count updated
    expect(screen.getByText(/3 of 2-5 labels selected/)).toBeInTheDocument();

    // 4. Remove a label
    const hikingOption = screen.getByText('hiking').closest('button');
    await user.click(hikingOption!);

    // 5. Verify count updated
    expect(screen.getByText(/2 of 2-5 labels selected/)).toBeInTheDocument();

    // 6. Save changes
    const saveButton = screen.getByRole('button', { name: 'Save' });
    await user.click(saveButton);

    // 7. Verify save was called with correct labels
    expect(mockOnSave).toHaveBeenCalledTimes(1);
    const savedLabels = mockOnSave.mock.calls[0][0] as string[];
    expect(savedLabels).toContain('trail-running');
    expect(savedLabels).toContain('camping');
    expect(savedLabels).not.toContain('hiking');
  });

  it('cancel workflow: changes are not saved', async () => {
    const user = userEvent.setup();

    render(
      <LabelEditDropdown
        taxonomyLabels={mockTaxonomyLabels}
        selectedLabels={['trail-running', 'hiking']}
        onLabelsChange={mockOnLabelsChange}
        onClose={mockOnClose}
        onSave={mockOnSave}
      />
    );

    // 1. Make some changes
    const campingOption = screen.getByText('camping').closest('button');
    await user.click(campingOption!);

    // 2. Cancel instead of save
    const cancelButton = screen.getByRole('button', { name: 'Cancel' });
    await user.click(cancelButton);

    // 3. Verify onSave was NOT called
    expect(mockOnSave).not.toHaveBeenCalled();

    // 4. Verify onClose was called
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('validation blocks save when selection invalid', async () => {
    const user = userEvent.setup();

    render(
      <LabelEditDropdown
        taxonomyLabels={mockTaxonomyLabels}
        selectedLabels={['trail-running', 'hiking']}
        onLabelsChange={mockOnLabelsChange}
        onClose={mockOnClose}
        onSave={mockOnSave}
      />
    );

    // Deselect labels to go below minimum
    const trailRunningOption = screen.getByText('trail-running').closest('button');
    await user.click(trailRunningOption!);

    // Now only 1 label selected - save should be disabled
    expect(screen.getByText(/Select at least 2 labels/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();

    // Try to click save (shouldn't work but let's verify)
    const saveButton = screen.getByRole('button', { name: 'Save' });
    await user.click(saveButton);

    // Verify save was NOT called
    expect(mockOnSave).not.toHaveBeenCalled();
  });
});
