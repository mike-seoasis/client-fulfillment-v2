import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { VoiceDimensionsSection } from '../VoiceDimensionsSection';

describe('VoiceDimensionsSection', () => {
  describe('slider position calculations', () => {
    it('renders position 1 at 0% (left edge)', () => {
      const data = {
        formality: {
          position: 1,
          description: 'Very casual',
        },
      };

      const { container } = render(<VoiceDimensionsSection data={data} />);

      // Check the position display text
      expect(screen.getByText('1/10')).toBeInTheDocument();

      // Check the slider fill width (position 1 = 0%)
      const sliderFill = container.querySelector('[class*="bg-gradient-to-r from-palm-300 to-palm-500"]');
      expect(sliderFill).toHaveStyle({ width: '0%' });

      // Check the position marker (left position = 0% - 8px)
      const marker = container.querySelector('[class*="bg-palm-500 border-2 border-white rounded-full"]');
      expect(marker).toHaveStyle({ left: 'calc(0% - 8px)' });
    });

    it('renders position 10 at 100% (right edge)', () => {
      const data = {
        formality: {
          position: 10,
          description: 'Very formal',
        },
      };

      const { container } = render(<VoiceDimensionsSection data={data} />);

      // Check the position display text
      expect(screen.getByText('10/10')).toBeInTheDocument();

      // Check the slider fill width (position 10 = 100%)
      const sliderFill = container.querySelector('[class*="bg-gradient-to-r from-palm-300 to-palm-500"]');
      expect(sliderFill).toHaveStyle({ width: '100%' });

      // Check the position marker
      const marker = container.querySelector('[class*="bg-palm-500 border-2 border-white rounded-full"]');
      expect(marker).toHaveStyle({ left: 'calc(100% - 8px)' });
    });

    it('renders position 5 at approximately 44.4% (middle)', () => {
      const data = {
        formality: {
          position: 5,
          description: 'Balanced formality',
        },
      };

      const { container } = render(<VoiceDimensionsSection data={data} />);

      // Check the position display text
      expect(screen.getByText('5/10')).toBeInTheDocument();

      // Position 5 calculation: ((5-1)/9) * 100 = 44.444...%
      const expectedPercent = ((5 - 1) / 9) * 100;
      const sliderFill = container.querySelector('[class*="bg-gradient-to-r from-palm-300 to-palm-500"]');
      expect(sliderFill).toHaveStyle({ width: `${expectedPercent}%` });
    });

    it('defaults undefined position to 5 (renders at ~44.4%)', () => {
      const data = {
        formality: {
          position: undefined as unknown as number,
          description: 'No position specified',
        },
      };

      const { container } = render(<VoiceDimensionsSection data={data} />);

      // Should display default position 5
      expect(screen.getByText('5/10')).toBeInTheDocument();

      // Default position 5: ((5-1)/9) * 100 = 44.444...%
      const expectedPercent = ((5 - 1) / 9) * 100;
      const sliderFill = container.querySelector('[class*="bg-gradient-to-r from-palm-300 to-palm-500"]');
      expect(sliderFill).toHaveStyle({ width: `${expectedPercent}%` });
    });

    it('defaults invalid string position to 5', () => {
      const data = {
        formality: {
          position: 'invalid' as unknown as number,
          description: 'Invalid position value',
        },
      };

      const { container } = render(<VoiceDimensionsSection data={data} />);

      // Should display default position 5
      expect(screen.getByText('5/10')).toBeInTheDocument();

      // Default position 5: ((5-1)/9) * 100 = 44.444...%
      const expectedPercent = ((5 - 1) / 9) * 100;
      const sliderFill = container.querySelector('[class*="bg-gradient-to-r from-palm-300 to-palm-500"]');
      expect(sliderFill).toHaveStyle({ width: `${expectedPercent}%` });
    });

    it('defaults NaN position to 5', () => {
      const data = {
        formality: {
          position: NaN,
          description: 'NaN position value',
        },
      };

      render(<VoiceDimensionsSection data={data} />);

      // Should display default position 5
      expect(screen.getByText('5/10')).toBeInTheDocument();
    });

    it('defaults out-of-range position (0) to 5', () => {
      const data = {
        formality: {
          position: 0,
          description: 'Below minimum',
        },
      };

      render(<VoiceDimensionsSection data={data} />);

      // Should display default position 5
      expect(screen.getByText('5/10')).toBeInTheDocument();
    });

    it('defaults out-of-range position (11) to 5', () => {
      const data = {
        formality: {
          position: 11,
          description: 'Above maximum',
        },
      };

      render(<VoiceDimensionsSection data={data} />);

      // Should display default position 5
      expect(screen.getByText('5/10')).toBeInTheDocument();
    });

    it('defaults negative position to 5', () => {
      const data = {
        formality: {
          position: -5,
          description: 'Negative position',
        },
      };

      render(<VoiceDimensionsSection data={data} />);

      // Should display default position 5
      expect(screen.getByText('5/10')).toBeInTheDocument();
    });
  });

  describe('dimension scale rendering', () => {
    it('renders all four dimension scales', () => {
      const data = {
        formality: { position: 3, description: 'Relaxed tone' },
        humor: { position: 7, description: 'More serious' },
        reverence: { position: 5, description: 'Balanced respect' },
        enthusiasm: { position: 8, description: 'Calm and steady' },
      };

      render(<VoiceDimensionsSection data={data} />);

      // Check all dimension labels
      expect(screen.getByText('Formality')).toBeInTheDocument();
      expect(screen.getByText('Humor')).toBeInTheDocument();
      expect(screen.getByText('Reverence')).toBeInTheDocument();
      expect(screen.getByText('Enthusiasm')).toBeInTheDocument();

      // Check scale labels (left/right labels for each dimension)
      expect(screen.getByText('Casual')).toBeInTheDocument();
      expect(screen.getByText('Formal')).toBeInTheDocument();
      expect(screen.getByText('Funny')).toBeInTheDocument();
      expect(screen.getByText('Serious')).toBeInTheDocument();
      expect(screen.getByText('Irreverent')).toBeInTheDocument();
      expect(screen.getByText('Respectful')).toBeInTheDocument();
      expect(screen.getByText('Enthusiastic')).toBeInTheDocument();
      expect(screen.getByText('Matter-of-Fact')).toBeInTheDocument();

      // Check descriptions are rendered
      expect(screen.getByText('Relaxed tone')).toBeInTheDocument();
      expect(screen.getByText('More serious')).toBeInTheDocument();
      expect(screen.getByText('Balanced respect')).toBeInTheDocument();
      expect(screen.getByText('Calm and steady')).toBeInTheDocument();
    });

    it('renders description when provided', () => {
      const data = {
        formality: {
          position: 3,
          description: 'We keep things casual and approachable',
        },
      };

      render(<VoiceDimensionsSection data={data} />);

      expect(screen.getByText('We keep things casual and approachable')).toBeInTheDocument();
    });

    it('renders example when provided', () => {
      const data = {
        formality: {
          position: 3,
          description: 'Casual tone',
          example: 'Hey there! Ready to get started?',
        },
      };

      render(<VoiceDimensionsSection data={data} />);

      expect(screen.getByText('Example:')).toBeInTheDocument();
      // The example is wrapped in quotes
      expect(screen.getByText(/Hey there! Ready to get started\?/)).toBeInTheDocument();
    });

    it('does not render dimension scale if scale is undefined', () => {
      const data = {
        formality: undefined,
        humor: { position: 5, description: 'Balanced humor' },
      };

      render(<VoiceDimensionsSection data={data} />);

      // Humor should be rendered
      expect(screen.getByText('Humor')).toBeInTheDocument();

      // Formality should not be rendered since its scale is undefined
      // We check that there's only one dimension header containing the dimension name
      const headers = screen.getAllByRole('heading', { level: 4 });
      expect(headers).toHaveLength(1);
      expect(headers[0]).toHaveTextContent('Humor');
    });
  });

  describe('voice summary rendering', () => {
    it('renders voice summary when provided', () => {
      const data = {
        formality: { position: 5 },
        voice_summary: 'Our voice is warm, friendly, and approachable.',
      };

      render(<VoiceDimensionsSection data={data} />);

      expect(screen.getByText('Voice Summary')).toBeInTheDocument();
      expect(screen.getByText('Our voice is warm, friendly, and approachable.')).toBeInTheDocument();
    });

    it('does not render voice summary section when not provided', () => {
      const data = {
        formality: { position: 5 },
      };

      render(<VoiceDimensionsSection data={data} />);

      expect(screen.queryByText('Voice Summary')).not.toBeInTheDocument();
    });
  });

  describe('empty/missing data handling', () => {
    it('shows empty message when data is undefined', () => {
      render(<VoiceDimensionsSection data={undefined} />);

      expect(screen.getByText('Voice dimensions data not available')).toBeInTheDocument();
    });

    it('shows empty message when no dimensions or summary configured', () => {
      const data = {
        formality: undefined,
        humor: undefined,
        reverence: undefined,
        enthusiasm: undefined,
        voice_summary: undefined,
      };

      render(<VoiceDimensionsSection data={data} />);

      expect(screen.getByText('Voice dimensions not configured')).toBeInTheDocument();
    });

    it('renders correctly with only voice_summary', () => {
      const data = {
        voice_summary: 'Just a summary, no dimensions.',
      };

      render(<VoiceDimensionsSection data={data} />);

      expect(screen.getByText('Voice Summary')).toBeInTheDocument();
      expect(screen.getByText('Just a summary, no dimensions.')).toBeInTheDocument();
    });
  });
});
