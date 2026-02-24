import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { VoiceCharacteristicsSection } from '../VoiceCharacteristicsSection';

describe('VoiceCharacteristicsSection', () => {
  describe('we_are_not data format handling', () => {
    it('handles we_are_not as string array format', () => {
      const data = {
        we_are: [
          {
            trait_name: 'Friendly',
            description: 'Warm and welcoming',
            do_example: 'Hi there!',
            dont_example: 'Dear Sir/Madam',
          },
        ],
        we_are_not: ['Corporate', 'Stuffy', 'Impersonal'],
      };

      render(<VoiceCharacteristicsSection data={data} />);

      // Check that string items are rendered correctly
      expect(screen.getByText('Corporate')).toBeInTheDocument();
      expect(screen.getByText('Stuffy')).toBeInTheDocument();
      expect(screen.getByText('Impersonal')).toBeInTheDocument();
    });

    it('handles we_are_not as object array format with trait_name', () => {
      const data = {
        we_are: [
          {
            trait_name: 'Friendly',
            description: 'Warm and welcoming',
          },
        ],
        // This format comes from the backend schema
        we_are_not: [
          { trait_name: 'Corporate' },
          { trait_name: 'Stuffy' },
          { trait_name: 'Impersonal' },
        ] as unknown as string[], // Type coercion to simulate backend response
      };

      render(<VoiceCharacteristicsSection data={data} />);

      // Check that object items with trait_name are rendered correctly
      expect(screen.getByText('Corporate')).toBeInTheDocument();
      expect(screen.getByText('Stuffy')).toBeInTheDocument();
      expect(screen.getByText('Impersonal')).toBeInTheDocument();
    });

    it('handles we_are_not as mixed format (strings and objects)', () => {
      const data = {
        we_are: [
          {
            trait_name: 'Friendly',
            description: 'Warm and welcoming',
          },
        ],
        // Mixed format: some strings, some objects
        we_are_not: [
          'Plain String Item',
          { trait_name: 'Object with trait_name' },
          'Another String',
        ] as unknown as string[], // Type coercion to simulate unexpected data
      };

      render(<VoiceCharacteristicsSection data={data} />);

      // Check that both formats are rendered
      expect(screen.getByText('Plain String Item')).toBeInTheDocument();
      expect(screen.getByText('Object with trait_name')).toBeInTheDocument();
      expect(screen.getByText('Another String')).toBeInTheDocument();
    });

    it('handles object items without trait_name by JSON stringifying', () => {
      const data = {
        we_are: [
          {
            trait_name: 'Friendly',
          },
        ],
        // Object without trait_name property
        we_are_not: [
          { some_other_property: 'value' },
        ] as unknown as string[],
      };

      render(<VoiceCharacteristicsSection data={data} />);

      // Should fall back to JSON.stringify
      expect(screen.getByText('{"some_other_property":"value"}')).toBeInTheDocument();
    });
  });

  describe('we_are trait rendering', () => {
    it('renders voice traits with all fields', () => {
      const data = {
        we_are: [
          {
            trait_name: 'Warm',
            description: 'Friendly and approachable',
            do_example: 'Welcome to our family!',
            dont_example: 'Dear valued customer',
          },
        ],
      };

      render(<VoiceCharacteristicsSection data={data} />);

      // Trait name is displayed (CSS transforms it to uppercase visually)
      expect(screen.getByRole('heading', { level: 4 })).toHaveTextContent('Warm');
      expect(screen.getByText('Friendly and approachable')).toBeInTheDocument();
      // Examples are wrapped in quotes
      expect(screen.getByText(/Welcome to our family!/)).toBeInTheDocument();
      expect(screen.getByText(/Dear valued customer/)).toBeInTheDocument();
    });
  });

  describe('empty/missing data handling', () => {
    it('shows empty message when data is undefined', () => {
      render(<VoiceCharacteristicsSection data={undefined} />);

      expect(screen.getByText('Voice characteristics data not available')).toBeInTheDocument();
    });

    it('shows empty message when we_are and we_are_not are both empty', () => {
      const data = {
        we_are: [],
        we_are_not: [],
      };

      render(<VoiceCharacteristicsSection data={data} />);

      expect(screen.getByText('Voice characteristics not configured')).toBeInTheDocument();
    });

    it('renders correctly when only we_are_not is provided', () => {
      const data = {
        we_are_not: ['Corporate', 'Boring'],
      };

      render(<VoiceCharacteristicsSection data={data} />);

      expect(screen.getByText('Corporate')).toBeInTheDocument();
      expect(screen.getByText('Boring')).toBeInTheDocument();
    });
  });
});
