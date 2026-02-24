import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import BrandConfigPage from '../page';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'project-123' }),
}));

// Mock project data
const mockProject = {
  id: 'project-123',
  name: 'Test Project',
  site_url: 'https://example.com',
  client_id: null,
  additional_info: null,
  status: 'active',
  phase_status: {},
  brand_config_status: 'complete',
  has_brand_config: true,
  uploaded_files_count: 2,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-15T10:30:00Z',
};

// Mock brand config data
const mockBrandConfig = {
  id: 'config-123',
  project_id: 'project-123',
  v2_schema: {
    brand_foundation: {
      company_overview: 'A tropical paradise company',
      positioning_statement: 'We are the best',
      mission: 'To provide excellent service',
      values: ['Quality', 'Innovation'],
      differentiators: ['Unique approach', 'Customer focus'],
    },
    target_audience: {
      personas: [
        {
          name: 'Beach Lover',
          demographics: { age_range: '25-40' },
          psychographics: { values: ['Adventure'] },
          behavioral: { buying_habits: ['Online'] },
        },
      ],
    },
    voice_dimensions: {
      formal_casual: { position: 5, anchor_left: 'Formal', anchor_right: 'Casual' },
      serious_playful: { position: 6, anchor_left: 'Serious', anchor_right: 'Playful' },
      respectful_irreverent: { position: 4, anchor_left: 'Respectful', anchor_right: 'Irreverent' },
      matter_of_fact_enthusiastic: { position: 7, anchor_left: 'Matter of Fact', anchor_right: 'Enthusiastic' },
    },
    voice_characteristics: {
      traits: [
        { trait: 'Friendly', description: 'Warm and welcoming', do_example: 'Hi there!', dont_example: 'Hello.' },
      ],
    },
    writing_style: {
      sentence_structure: ['Short and punchy'],
      capitalization_rules: ['Title case for headings'],
      punctuation_preferences: ['Use exclamation points sparingly'],
    },
    vocabulary: {
      power_words: ['Amazing', 'Transform'],
      substitutions: [{ avoid: 'cheap', prefer: 'affordable' }],
      banned_words: ['Never use this'],
      industry_terms: ['Technical term'],
    },
    trust_elements: {
      hard_numbers: ['100% satisfaction'],
      credentials: ['ISO certified'],
      guarantees: ['Money back guarantee'],
      customer_quotes: ['Best service ever!'],
    },
    examples_bank: {
      headlines: ['Your Dream Vacation Awaits'],
      product_descriptions: ['Experience paradise'],
      ctas: ['Book Now'],
      off_brand_examples: [{ example: 'Bad copy', reason: 'Too aggressive' }],
    },
    competitor_context: {
      competitors: [{ name: 'Competitor A', positioning: 'Budget option', voice_notes: 'Very formal' }],
      advantages: ['Better service'],
      positioning_statements: ['Premium quality'],
    },
    ai_prompt_snippet: 'You are a friendly travel brand assistant...',
  },
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-15T10:30:00Z',
};

// Mock files data
const mockFilesData = {
  items: [
    { id: 'file-1', filename: 'brand-guide.pdf', content_type: 'application/pdf', file_size: 1024 },
    { id: 'file-2', filename: 'style-notes.docx', content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', file_size: 2048 },
  ],
  total: 2,
};

// Mock hooks
const mockUseProject = vi.fn();
const mockUseBrandConfig = vi.fn();
const mockUseProjectFiles = vi.fn();
const mockUseRegenerateBrandConfig = vi.fn();
const mockUseUpdateBrandConfig = vi.fn();

vi.mock('@/hooks/use-projects', () => ({
  useProject: () => mockUseProject(),
}));

vi.mock('@/hooks/useBrandConfig', () => ({
  useBrandConfig: () => mockUseBrandConfig(),
  useRegenerateBrandConfig: () => mockUseRegenerateBrandConfig(),
  useUpdateBrandConfig: () => mockUseUpdateBrandConfig(),
}));

vi.mock('@/hooks/useProjectFiles', () => ({
  useProjectFiles: () => mockUseProjectFiles(),
}));

describe('BrandConfigPage', () => {
  const createMockMutation = (overrides = {}) => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    error: null,
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();

    // Default successful state
    mockUseProject.mockReturnValue({
      data: mockProject,
      isLoading: false,
      error: null,
    });

    mockUseBrandConfig.mockReturnValue({
      data: mockBrandConfig,
      isLoading: false,
      error: null,
    });

    mockUseProjectFiles.mockReturnValue({
      data: mockFilesData,
      isLoading: false,
      error: null,
    });

    mockUseRegenerateBrandConfig.mockReturnValue(createMockMutation());
    mockUseUpdateBrandConfig.mockReturnValue(createMockMutation());
  });

  describe('loading state', () => {
    it('renders loading skeleton when project is loading', () => {
      mockUseProject.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });

      render(<BrandConfigPage />);

      // Loading skeleton includes "Back to Project" link
      expect(screen.getByText('Back to Project')).toBeInTheDocument();
      // Skeleton has animated elements
      expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
    });

    it('renders loading skeleton when brand config is loading', () => {
      mockUseBrandConfig.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });

      render(<BrandConfigPage />);

      expect(document.querySelector('.animate-pulse')).toBeInTheDocument();
    });
  });

  describe('error states', () => {
    it('renders project not found state when project fetch fails', () => {
      mockUseProject.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Not found'),
      });

      render(<BrandConfigPage />);

      expect(screen.getByText('Project Not Found')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Back to Dashboard' })).toBeInTheDocument();
    });

    it('renders brand config not found state when brand config fetch fails', () => {
      mockUseBrandConfig.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Not found'),
      });

      render(<BrandConfigPage />);

      expect(screen.getByText('Brand Configuration Not Found')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Back to Projects' })).toBeInTheDocument();
    });
  });

  describe('successful render', () => {
    it('renders page header with title and project name', () => {
      render(<BrandConfigPage />);

      expect(screen.getByText('Brand Configuration')).toBeInTheDocument();
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });

    it('renders back link to project page', () => {
      render(<BrandConfigPage />);

      const backLink = screen.getByText('Back to Project');
      expect(backLink).toBeInTheDocument();
      expect(backLink.closest('a')).toHaveAttribute('href', '/projects/project-123');
    });

    it('renders Regenerate All button', () => {
      render(<BrandConfigPage />);

      expect(screen.getByRole('button', { name: /Regenerate All/ })).toBeInTheDocument();
    });
  });

  describe('section navigation', () => {
    it('renders all 10 section tabs', () => {
      render(<BrandConfigPage />);

      expect(screen.getByRole('button', { name: 'Brand Foundation' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Target Audience' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Voice Dimensions' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Voice Characteristics' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Writing Style' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Vocabulary' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Trust Elements' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Examples Bank' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Competitor Context' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'AI Prompt' })).toBeInTheDocument();
    });

    it('shows Brand Foundation as default active section', () => {
      render(<BrandConfigPage />);

      // The section header shows the active section label
      const sectionHeaders = screen.getAllByRole('heading', { level: 2 });
      const contentHeader = sectionHeaders.find(h => h.textContent === 'Brand Foundation');
      expect(contentHeader).toBeInTheDocument();
    });

    it('changes active section when tab is clicked', async () => {
      const user = userEvent.setup();
      render(<BrandConfigPage />);

      await user.click(screen.getByRole('button', { name: 'Target Audience' }));

      // Check that the content area heading changed
      await waitFor(() => {
        const sectionHeaders = screen.getAllByRole('heading', { level: 2 });
        const contentHeader = sectionHeaders.find(h => h.textContent === 'Target Audience');
        expect(contentHeader).toBeInTheDocument();
      });
    });
  });

  describe('source documents', () => {
    it('renders source documents list', () => {
      render(<BrandConfigPage />);

      expect(screen.getByText('brand-guide.pdf')).toBeInTheDocument();
      expect(screen.getByText('style-notes.docx')).toBeInTheDocument();
    });

    it('shows "No documents uploaded" when no files', () => {
      mockUseProjectFiles.mockReturnValue({
        data: { items: [], total: 0 },
        isLoading: false,
        error: null,
      });

      render(<BrandConfigPage />);

      expect(screen.getByText('No documents uploaded')).toBeInTheDocument();
    });
  });

  describe('regenerate functionality', () => {
    it('calls regenerate mutation when Regenerate All is clicked', async () => {
      const mockMutate = vi.fn();
      mockUseRegenerateBrandConfig.mockReturnValue(createMockMutation({ mutate: mockMutate }));

      const user = userEvent.setup();
      render(<BrandConfigPage />);

      await user.click(screen.getByRole('button', { name: /Regenerate All/ }));

      expect(mockMutate).toHaveBeenCalledWith(undefined, expect.any(Object));
    });

    it('shows loading state when Regenerate All is in progress', () => {
      mockUseRegenerateBrandConfig.mockReturnValue(createMockMutation({ isPending: true }));

      render(<BrandConfigPage />);

      expect(screen.getByRole('button', { name: /Regenerating.../ })).toBeDisabled();
    });

    it('calls regenerate mutation with section when section Regenerate is clicked', async () => {
      const mockMutate = vi.fn();
      mockUseRegenerateBrandConfig.mockReturnValue(createMockMutation({ mutate: mockMutate }));

      const user = userEvent.setup();
      render(<BrandConfigPage />);

      // Find and click the section-level Regenerate button (not Regenerate All)
      const regenerateButtons = screen.getAllByRole('button', { name: /^Regenerate$/ });
      await user.click(regenerateButtons[0]);

      expect(mockMutate).toHaveBeenCalledWith(
        { section: 'brand_foundation' },
        expect.any(Object)
      );
    });

    it('calls regenerate with target_audience when regenerating that section', async () => {
      const mockMutate = vi.fn();
      mockUseRegenerateBrandConfig.mockReturnValue(createMockMutation({ mutate: mockMutate }));

      const user = userEvent.setup();
      render(<BrandConfigPage />);

      // Navigate to Target Audience section
      await user.click(screen.getByRole('button', { name: 'Target Audience' }));
      await waitFor(() => {
        const sectionHeaders = screen.getAllByRole('heading', { level: 2 });
        const contentHeader = sectionHeaders.find(h => h.textContent === 'Target Audience');
        expect(contentHeader).toBeInTheDocument();
      });

      // Click Regenerate button for the section
      const regenerateButtons = screen.getAllByRole('button', { name: /^Regenerate$/ });
      await user.click(regenerateButtons[0]);

      expect(mockMutate).toHaveBeenCalledWith(
        { section: 'target_audience' },
        expect.any(Object)
      );
    });

    it('calls regenerate with examples_bank when regenerating that section', async () => {
      const mockMutate = vi.fn();
      mockUseRegenerateBrandConfig.mockReturnValue(createMockMutation({ mutate: mockMutate }));

      const user = userEvent.setup();
      render(<BrandConfigPage />);

      // Navigate to Examples Bank section
      await user.click(screen.getByRole('button', { name: 'Examples Bank' }));
      await waitFor(() => {
        const sectionHeaders = screen.getAllByRole('heading', { level: 2 });
        const contentHeader = sectionHeaders.find(h => h.textContent === 'Examples Bank');
        expect(contentHeader).toBeInTheDocument();
      });

      // Click Regenerate button for the section
      const regenerateButtons = screen.getAllByRole('button', { name: /^Regenerate$/ });
      await user.click(regenerateButtons[0]);

      expect(mockMutate).toHaveBeenCalledWith(
        { section: 'examples_bank' },
        expect.any(Object)
      );
    });
  });

  describe('edit functionality', () => {
    it('renders Edit button for active section', () => {
      render(<BrandConfigPage />);

      expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
    });

    it('shows editor when Edit is clicked', async () => {
      const user = userEvent.setup();
      render(<BrandConfigPage />);

      await user.click(screen.getByRole('button', { name: 'Edit' }));

      // Editor shows textarea and Save/Cancel buttons
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Save Changes' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
      });
    });

    it('hides Edit button when in edit mode', async () => {
      const user = userEvent.setup();
      render(<BrandConfigPage />);

      await user.click(screen.getByRole('button', { name: 'Edit' }));

      await waitFor(() => {
        // Edit button should not be visible in edit mode
        const editButtons = screen.queryAllByRole('button', { name: 'Edit' });
        expect(editButtons).toHaveLength(0);
      });
    });

    it('exits edit mode when Cancel is clicked', async () => {
      const user = userEvent.setup();
      render(<BrandConfigPage />);

      await user.click(screen.getByRole('button', { name: 'Edit' }));
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: 'Cancel' }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
      });
    });

    it('exits edit mode when changing sections', async () => {
      const user = userEvent.setup();
      render(<BrandConfigPage />);

      // Enter edit mode
      await user.click(screen.getByRole('button', { name: 'Edit' }));
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
      });

      // Change section
      await user.click(screen.getByRole('button', { name: 'Target Audience' }));

      // Should exit edit mode
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
      });
    });

    it('calls update mutation when Save is clicked', async () => {
      const mockMutate = vi.fn();
      mockUseUpdateBrandConfig.mockReturnValue(createMockMutation({ mutate: mockMutate }));

      const user = userEvent.setup();
      render(<BrandConfigPage />);

      await user.click(screen.getByRole('button', { name: 'Edit' }));
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Save Changes' })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: 'Save Changes' }));

      expect(mockMutate).toHaveBeenCalledWith(
        expect.objectContaining({
          sections: expect.objectContaining({
            brand_foundation: expect.any(Object),
          }),
        }),
        expect.any(Object)
      );
    });
  });

  describe('toast notifications', () => {
    it('shows success toast after successful regeneration', async () => {
      const mockMutate = vi.fn().mockImplementation((_, options) => {
        options?.onSuccess?.();
      });
      mockUseRegenerateBrandConfig.mockReturnValue(createMockMutation({ mutate: mockMutate }));

      const user = userEvent.setup();
      render(<BrandConfigPage />);

      await user.click(screen.getByRole('button', { name: /Regenerate All/ }));

      await waitFor(() => {
        expect(screen.getByText('All sections regenerated successfully')).toBeInTheDocument();
      });
    });

    it('shows section-specific success toast after section regeneration', async () => {
      const mockMutate = vi.fn().mockImplementation((_, options) => {
        options?.onSuccess?.();
      });
      mockUseRegenerateBrandConfig.mockReturnValue(createMockMutation({ mutate: mockMutate }));

      const user = userEvent.setup();
      render(<BrandConfigPage />);

      const regenerateButtons = screen.getAllByRole('button', { name: /^Regenerate$/ });
      await user.click(regenerateButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('Brand Foundation regenerated successfully')).toBeInTheDocument();
      });
    });

    it('shows success toast after successful save', async () => {
      const mockMutate = vi.fn().mockImplementation((_, options) => {
        options?.onSuccess?.();
      });
      mockUseUpdateBrandConfig.mockReturnValue(createMockMutation({ mutate: mockMutate }));

      const user = userEvent.setup();
      render(<BrandConfigPage />);

      await user.click(screen.getByRole('button', { name: 'Edit' }));
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Save Changes' })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: 'Save Changes' }));

      await waitFor(() => {
        expect(screen.getByText('Section saved successfully')).toBeInTheDocument();
      });
    });
  });
});
