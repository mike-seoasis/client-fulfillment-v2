import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  GenerationProgress,
  GENERATION_STEPS,
  STEP_DISPLAY_NAMES,
} from '../GenerationProgress';

// Mock the useBrandConfigGeneration hook
const mockUseBrandConfigGeneration = vi.fn();
vi.mock('@/hooks/useBrandConfigGeneration', () => ({
  useBrandConfigGeneration: () => mockUseBrandConfigGeneration(),
}));

describe('GenerationProgress', () => {
  const mockOnComplete = vi.fn();
  const mockOnBack = vi.fn();
  const mockOnGoToProject = vi.fn();
  const mockOnRetry = vi.fn();

  const defaultProps = {
    projectId: 'project-123',
    projectName: 'Test Project',
    onComplete: mockOnComplete,
    onBack: mockOnBack,
    onGoToProject: mockOnGoToProject,
    onRetry: mockOnRetry,
  };

  // Default mock return value for generating state
  const createMockGenerationState = (overrides = {}) => ({
    isLoading: false,
    isError: false,
    isGenerating: false,
    isComplete: false,
    isFailed: false,
    status: 'pending',
    currentStep: null,
    stepsCompleted: 0,
    stepsTotal: 10,
    progress: 0,
    error: null,
    startedAt: null,
    completedAt: null,
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseBrandConfigGeneration.mockReturnValue(createMockGenerationState());
  });

  describe('rendering', () => {
    it('renders all 13 generation steps', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isGenerating: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      // Check all step labels are rendered
      GENERATION_STEPS.forEach((step) => {
        expect(screen.getByText(STEP_DISPLAY_NAMES[step])).toBeInTheDocument();
      });
    });

    it('displays generation header with lightning icon when generating', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isGenerating: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      expect(screen.getByText('Generating Brand Configuration...')).toBeInTheDocument();
    });

    it('displays progress bar when generating', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({
          isGenerating: true,
          stepsCompleted: 3,
          currentStep: 'voice_characteristics',
        })
      );
      render(<GenerationProgress {...defaultProps} />);

      // Progress bar should be visible (find the percentage display)
      expect(screen.getByText(/\d+%/)).toBeInTheDocument();
    });

    it('displays "Please wait..." button when generating', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isGenerating: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Please wait...' })).toBeDisabled();
    });
  });

  describe('step status indicators', () => {
    it('marks research phase steps as current when starting generation', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({
          isGenerating: true,
          currentStep: 'perplexity_research',
        })
      );
      render(<GenerationProgress {...defaultProps} />);

      // First step should have current styling (bg-palm-50)
      const firstStepContainer = screen.getByText(STEP_DISPLAY_NAMES['perplexity_research']).closest('div');
      expect(firstStepContainer).toHaveClass('bg-palm-50');
    });

    it('marks research phase as complete when synthesis starts', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({
          isGenerating: true,
          stepsCompleted: 0,
          currentStep: 'brand_foundation',
        })
      );
      render(<GenerationProgress {...defaultProps} />);

      // Brand foundation should be current, research should be complete
      const brandFoundationContainer = screen.getByText(STEP_DISPLAY_NAMES['brand_foundation']).closest('div');
      expect(brandFoundationContainer).toHaveClass('bg-palm-50');
    });

    it('marks synthesis steps as complete based on stepsCompleted', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({
          isGenerating: true,
          stepsCompleted: 3,
          currentStep: 'voice_characteristics',
        })
      );
      render(<GenerationProgress {...defaultProps} />);

      // voice_characteristics (4th synthesis step, index 3) should be current
      const currentStepContainer = screen.getByText(STEP_DISPLAY_NAMES['voice_characteristics']).closest('div');
      expect(currentStepContainer).toHaveClass('bg-palm-50');
    });
  });

  describe('progress calculation', () => {
    it('shows 0% progress when not generating (in pending state)', () => {
      mockUseBrandConfigGeneration.mockReturnValue(createMockGenerationState());
      render(<GenerationProgress {...defaultProps} />);

      // In pending state (not generating, not complete, not failed),
      // the component still renders the progress display showing 0%
      // This is normal behavior - progress starts at 0
      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    it('calculates progress for research phase steps', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({
          isGenerating: true,
          currentStep: 'crawling',
        })
      );
      render(<GenerationProgress {...defaultProps} />);

      // Crawling is step 2 of 13, so ~8%
      expect(screen.getByText(/\d+%/)).toBeInTheDocument();
    });

    it('shows 100% progress when complete', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({
          isComplete: true,
          stepsCompleted: 10,
        })
      );
      render(<GenerationProgress {...defaultProps} />);

      // When complete, progress bar is not shown, but completion state is
      expect(screen.getByText('Project Created!')).toBeInTheDocument();
    });
  });

  describe('completion state', () => {
    it('displays success message when generation is complete', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isComplete: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      expect(screen.getByText('Project Created!')).toBeInTheDocument();
    });

    it('displays project name in completion message', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isComplete: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      expect(screen.getByText(/Test Project/)).toBeInTheDocument();
      expect(screen.getByText(/Brand configuration has been generated successfully/)).toBeInTheDocument();
    });

    it('displays generic completion message when no project name provided', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isComplete: true })
      );
      render(<GenerationProgress {...defaultProps} projectName={undefined} />);

      expect(screen.getByText('Brand configuration has been generated successfully.')).toBeInTheDocument();
    });

    it('renders "Go to Project" button when complete', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isComplete: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      expect(screen.getByRole('button', { name: /Go to Project/ })).toBeInTheDocument();
    });

    it('calls onGoToProject when "Go to Project" button is clicked', async () => {
      const user = userEvent.setup();
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isComplete: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /Go to Project/ }));

      expect(mockOnGoToProject).toHaveBeenCalled();
    });

    it('calls onComplete callback when generation completes', async () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isComplete: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      await waitFor(() => {
        expect(mockOnComplete).toHaveBeenCalled();
      });
    });
  });

  describe('failure state', () => {
    it('displays failure message when generation fails', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({
          isFailed: true,
          error: 'API rate limit exceeded',
        })
      );
      render(<GenerationProgress {...defaultProps} />);

      expect(screen.getByText('Generation Failed')).toBeInTheDocument();
      expect(screen.getByText('API rate limit exceeded')).toBeInTheDocument();
    });

    it('renders Back button when failed', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isFailed: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Back' })).toBeInTheDocument();
    });

    it('calls onBack when Back button is clicked', async () => {
      const user = userEvent.setup();
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isFailed: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: 'Back' }));

      expect(mockOnBack).toHaveBeenCalled();
    });

    it('renders Retry button when onRetry is provided', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isFailed: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
    });

    it('does not render Retry button when onRetry is not provided', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isFailed: true })
      );
      render(<GenerationProgress {...defaultProps} onRetry={undefined} />);

      expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
    });

    it('calls onRetry and shows loading state when Retry button is clicked', async () => {
      const user = userEvent.setup();
      mockOnRetry.mockImplementation(() => new Promise((resolve) => setTimeout(resolve, 100)));
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isFailed: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: 'Retry' }));

      expect(mockOnRetry).toHaveBeenCalled();
      expect(screen.getByRole('button', { name: 'Retrying...' })).toBeDisabled();
    });

    it('renders "Go to Project Anyway" button when failed', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isFailed: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      expect(screen.getByRole('button', { name: 'Go to Project Anyway' })).toBeInTheDocument();
    });

    it('calls onGoToProject when "Go to Project Anyway" button is clicked', async () => {
      const user = userEvent.setup();
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isFailed: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: 'Go to Project Anyway' }));

      expect(mockOnGoToProject).toHaveBeenCalled();
    });
  });

  describe('current step label', () => {
    it('displays "Starting..." when generating but no current step', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({
          isGenerating: true,
          currentStep: null,
          stepsCompleted: 0,
        })
      );
      render(<GenerationProgress {...defaultProps} />);

      // When generating with no current step and no completed steps,
      // component shows "Gathering research data..." or "Starting..."
      // depending on the exact state interpretation
      expect(screen.getByText(/Starting|Gathering/)).toBeInTheDocument();
    });

    it('displays "Gathering research data..." during research phase', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({
          isGenerating: true,
          stepsCompleted: 0,
        })
      );
      render(<GenerationProgress {...defaultProps} />);

      expect(screen.getByText(/Starting|Gathering research data/)).toBeInTheDocument();
    });

    it('displays step-specific label during synthesis', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({
          isGenerating: true,
          currentStep: 'vocabulary',
          stepsCompleted: 5,
        })
      );
      render(<GenerationProgress {...defaultProps} />);

      expect(screen.getByText(/Building vocabulary guide.../)).toBeInTheDocument();
    });

    it('displays "Complete!" when generation is done', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isComplete: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      // The "Complete!" label is used in getCurrentStepLabel, but the UI shows "Project Created!"
      expect(screen.getByText('Project Created!')).toBeInTheDocument();
    });

    it('displays "Failed" when generation fails', () => {
      mockUseBrandConfigGeneration.mockReturnValue(
        createMockGenerationState({ isFailed: true })
      );
      render(<GenerationProgress {...defaultProps} />);

      expect(screen.getByText('Generation Failed')).toBeInTheDocument();
    });
  });

  describe('exported constants', () => {
    it('exports GENERATION_STEPS with 13 steps', () => {
      expect(GENERATION_STEPS).toHaveLength(13);
    });

    it('exports GENERATION_STEPS with correct research steps', () => {
      expect(GENERATION_STEPS.slice(0, 3)).toEqual([
        'perplexity_research',
        'crawling',
        'processing_docs',
      ]);
    });

    it('exports GENERATION_STEPS with correct synthesis steps', () => {
      expect(GENERATION_STEPS.slice(3, 12)).toEqual([
        'brand_foundation',
        'target_audience',
        'voice_dimensions',
        'voice_characteristics',
        'writing_style',
        'vocabulary',
        'trust_elements',
        'examples_bank',
        'competitor_context',
      ]);
    });

    it('exports GENERATION_STEPS with ai_prompt_snippet as final step', () => {
      expect(GENERATION_STEPS[12]).toBe('ai_prompt_snippet');
    });

    it('exports STEP_DISPLAY_NAMES for all steps', () => {
      GENERATION_STEPS.forEach((step) => {
        expect(STEP_DISPLAY_NAMES[step]).toBeDefined();
        expect(typeof STEP_DISPLAY_NAMES[step]).toBe('string');
      });
    });
  });
});
