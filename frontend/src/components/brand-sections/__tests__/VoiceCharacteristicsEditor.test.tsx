import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { VoiceCharacteristicsEditor } from '../editors/VoiceCharacteristicsEditor';

describe('VoiceCharacteristicsEditor', () => {
  const defaultProps = {
    onSave: vi.fn(),
    onCancel: vi.fn(),
    isSaving: false,
  };

  describe('we_are_not data format handling', () => {
    it('initializes correctly with we_are_not as string array', () => {
      const data = {
        we_are: [
          {
            trait_name: 'Friendly',
            description: 'Warm and welcoming',
          },
        ],
        we_are_not: ['Corporate', 'Stuffy', 'Impersonal'],
      };

      render(<VoiceCharacteristicsEditor {...defaultProps} data={data} />);

      // BulletListEditor displays items as text spans, not input values
      expect(screen.getByText('Corporate')).toBeInTheDocument();
      expect(screen.getByText('Stuffy')).toBeInTheDocument();
      expect(screen.getByText('Impersonal')).toBeInTheDocument();
    });

    it('initializes correctly with we_are_not as object array format', () => {
      const data = {
        we_are: [
          {
            trait_name: 'Friendly',
          },
        ],
        // Backend schema format: objects with trait_name
        we_are_not: [
          { trait_name: 'Corporate' },
          { trait_name: 'Stuffy' },
          { trait_name: 'Impersonal' },
        ] as unknown as string[],
      };

      render(<VoiceCharacteristicsEditor {...defaultProps} data={data} />);

      // Should extract trait_name from objects and display as text
      expect(screen.getByText('Corporate')).toBeInTheDocument();
      expect(screen.getByText('Stuffy')).toBeInTheDocument();
      expect(screen.getByText('Impersonal')).toBeInTheDocument();
    });

    it('initializes correctly with we_are_not as mixed format', () => {
      const data = {
        we_are: [
          {
            trait_name: 'Friendly',
          },
        ],
        // Mixed: strings and objects
        we_are_not: [
          'Plain String',
          { trait_name: 'Object Value' },
          'Another String',
        ] as unknown as string[],
      };

      render(<VoiceCharacteristicsEditor {...defaultProps} data={data} />);

      // Should handle both formats
      expect(screen.getByText('Plain String')).toBeInTheDocument();
      expect(screen.getByText('Object Value')).toBeInTheDocument();
      expect(screen.getByText('Another String')).toBeInTheDocument();
    });

    it('handles object without trait_name gracefully', () => {
      const data = {
        we_are: [
          {
            trait_name: 'Friendly',
          },
        ],
        // Object without trait_name - will become empty string
        we_are_not: [
          { some_other_prop: 'value' },
        ] as unknown as string[],
      };

      render(<VoiceCharacteristicsEditor {...defaultProps} data={data} />);

      // Should render without crashing
      // The item will be an empty string which won't be visible
      expect(screen.getByDisplayValue('Friendly')).toBeInTheDocument();
    });
  });

  describe('saving normalized data', () => {
    it('saves we_are_not as string array regardless of input format', async () => {
      const onSave = vi.fn();
      const user = userEvent.setup();

      const data = {
        we_are: [
          {
            trait_name: 'Friendly',
          },
        ],
        // Object format from backend
        we_are_not: [
          { trait_name: 'Corporate' },
        ] as unknown as string[],
      };

      render(<VoiceCharacteristicsEditor {...defaultProps} data={data} onSave={onSave} />);

      // Click save
      await user.click(screen.getByRole('button', { name: 'Save Changes' }));

      // Verify the saved data has we_are_not as string array
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({
          we_are_not: ['Corporate'], // Should be normalized to string array
        })
      );
    });
  });

  describe('editing we_are traits', () => {
    it('allows editing trait name', async () => {
      const user = userEvent.setup();
      const data = {
        we_are: [
          {
            trait_name: 'Original',
            description: 'Test description',
          },
        ],
      };

      render(<VoiceCharacteristicsEditor {...defaultProps} data={data} />);

      const traitNameInput = screen.getByDisplayValue('Original');
      await user.clear(traitNameInput);
      await user.type(traitNameInput, 'Updated');

      expect(screen.getByDisplayValue('Updated')).toBeInTheDocument();
    });
  });

  describe('empty data handling', () => {
    it('initializes with empty arrays when data is undefined', () => {
      render(<VoiceCharacteristicsEditor {...defaultProps} data={undefined} />);

      // Should show the "Add Your First Trait" button
      expect(screen.getByRole('button', { name: /Add Your First Trait/i })).toBeInTheDocument();
    });

    it('initializes with empty arrays when we_are_not is undefined', () => {
      const data = {
        we_are: [{ trait_name: 'Friendly' }],
        // we_are_not is undefined
      };

      render(<VoiceCharacteristicsEditor {...defaultProps} data={data} />);

      // Should render without crashing
      expect(screen.getByDisplayValue('Friendly')).toBeInTheDocument();
    });
  });
});
