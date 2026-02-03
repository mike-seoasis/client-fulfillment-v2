import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ProjectForm } from '../ProjectForm';

describe('ProjectForm', () => {
  const mockOnSubmit = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the project name input', () => {
      render(<ProjectForm onSubmit={mockOnSubmit} />);

      expect(screen.getByLabelText('Project Name')).toBeInTheDocument();
    });

    it('renders the site URL input', () => {
      render(<ProjectForm onSubmit={mockOnSubmit} />);

      expect(screen.getByLabelText('Site URL')).toBeInTheDocument();
    });

    it('renders Create Project button when no initialData', () => {
      render(<ProjectForm onSubmit={mockOnSubmit} />);

      expect(screen.getByRole('button', { name: 'Create Project' })).toBeInTheDocument();
    });

    it('renders Update Project button when initialData provided', () => {
      render(
        <ProjectForm
          onSubmit={mockOnSubmit}
          initialData={{ name: 'Test', site_url: 'https://example.com' }}
        />
      );

      expect(screen.getByRole('button', { name: 'Update Project' })).toBeInTheDocument();
    });

    it('shows Saving... when isSubmitting is true', () => {
      render(<ProjectForm onSubmit={mockOnSubmit} isSubmitting />);

      expect(screen.getByRole('button', { name: 'Saving...' })).toBeInTheDocument();
    });

    it('populates fields with initialData', () => {
      render(
        <ProjectForm
          onSubmit={mockOnSubmit}
          initialData={{ name: 'My Project', site_url: 'https://mysite.com' }}
        />
      );

      expect(screen.getByLabelText('Project Name')).toHaveValue('My Project');
      expect(screen.getByLabelText('Site URL')).toHaveValue('https://mysite.com');
    });
  });

  describe('validation - required fields', () => {
    it('shows error when name is empty', async () => {
      const user = userEvent.setup();
      render(<ProjectForm onSubmit={mockOnSubmit} />);

      // Fill in URL but leave name empty
      await user.type(screen.getByLabelText('Site URL'), 'https://example.com');
      await user.click(screen.getByRole('button', { name: 'Create Project' }));

      await waitFor(() => {
        expect(screen.getByText('Project name is required')).toBeInTheDocument();
      });

      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('shows error when site_url is empty', async () => {
      const user = userEvent.setup();
      render(<ProjectForm onSubmit={mockOnSubmit} />);

      // Fill in name but leave URL empty
      await user.type(screen.getByLabelText('Project Name'), 'Test Project');
      await user.click(screen.getByRole('button', { name: 'Create Project' }));

      await waitFor(() => {
        expect(screen.getByText('Please enter a valid URL')).toBeInTheDocument();
      });

      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('shows both errors when both fields are empty', async () => {
      const user = userEvent.setup();
      render(<ProjectForm onSubmit={mockOnSubmit} />);

      await user.click(screen.getByRole('button', { name: 'Create Project' }));

      await waitFor(() => {
        expect(screen.getByText('Project name is required')).toBeInTheDocument();
        expect(screen.getByText('Please enter a valid URL')).toBeInTheDocument();
      });

      expect(mockOnSubmit).not.toHaveBeenCalled();
    });
  });

  describe('validation - URL format', () => {
    // Note: Tests for invalid URL format (e.g., "not-a-valid-url", "example.com")
    // are handled by browser's native type="url" validation which blocks form
    // submission before react-hook-form validation runs. The Zod schema provides
    // server-side validation and catches empty strings via "Please enter a valid URL".

    it('validates URL format via Zod schema (empty string)', async () => {
      const user = userEvent.setup();
      render(<ProjectForm onSubmit={mockOnSubmit} />);

      await user.type(screen.getByLabelText('Project Name'), 'Test Project');
      // Leave URL empty - this triggers Zod validation
      await user.click(screen.getByRole('button', { name: 'Create Project' }));

      await waitFor(() => {
        expect(screen.getByText('Please enter a valid URL')).toBeInTheDocument();
      });

      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('accepts valid https URL and submits', async () => {
      const user = userEvent.setup();
      render(<ProjectForm onSubmit={mockOnSubmit} />);

      await user.type(screen.getByLabelText('Project Name'), 'Test Project');
      await user.type(screen.getByLabelText('Site URL'), 'https://example.com');

      // Use fireEvent.submit to bypass native validation in jsdom
      const form = screen.getByRole('button', { name: 'Create Project' }).closest('form')!;
      fireEvent.submit(form);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled();
        // react-hook-form passes (data, event) - check first argument
        expect(mockOnSubmit.mock.calls[0][0]).toEqual({
          name: 'Test Project',
          site_url: 'https://example.com',
        });
      });
    });

    it('accepts valid http URL and submits', async () => {
      const user = userEvent.setup();
      render(<ProjectForm onSubmit={mockOnSubmit} />);

      await user.type(screen.getByLabelText('Project Name'), 'Test Project');
      await user.type(screen.getByLabelText('Site URL'), 'http://example.com');

      const form = screen.getByRole('button', { name: 'Create Project' }).closest('form')!;
      fireEvent.submit(form);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled();
        expect(mockOnSubmit.mock.calls[0][0]).toEqual({
          name: 'Test Project',
          site_url: 'http://example.com',
        });
      });
    });

    it('accepts URL with path and query params', async () => {
      const user = userEvent.setup();
      render(<ProjectForm onSubmit={mockOnSubmit} />);

      await user.type(screen.getByLabelText('Project Name'), 'Test Project');
      await user.type(screen.getByLabelText('Site URL'), 'https://example.com/path?query=1');

      const form = screen.getByRole('button', { name: 'Create Project' }).closest('form')!;
      fireEvent.submit(form);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled();
        expect(mockOnSubmit.mock.calls[0][0]).toEqual({
          name: 'Test Project',
          site_url: 'https://example.com/path?query=1',
        });
      });
    });

    it('rejects invalid URL format via Zod validation', async () => {
      const user = userEvent.setup();
      render(<ProjectForm onSubmit={mockOnSubmit} />);

      await user.type(screen.getByLabelText('Project Name'), 'Test Project');
      // Type invalid URL and manually set value to bypass native validation
      const urlInput = screen.getByLabelText('Site URL');
      fireEvent.change(urlInput, { target: { value: 'not-a-valid-url' } });

      const form = screen.getByRole('button', { name: 'Create Project' }).closest('form')!;
      fireEvent.submit(form);

      await waitFor(() => {
        expect(screen.getByText('Please enter a valid URL')).toBeInTheDocument();
      });

      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    it('rejects URL without protocol via Zod validation', async () => {
      const user = userEvent.setup();
      render(<ProjectForm onSubmit={mockOnSubmit} />);

      await user.type(screen.getByLabelText('Project Name'), 'Test Project');
      const urlInput = screen.getByLabelText('Site URL');
      fireEvent.change(urlInput, { target: { value: 'example.com' } });

      const form = screen.getByRole('button', { name: 'Create Project' }).closest('form')!;
      fireEvent.submit(form);

      await waitFor(() => {
        expect(screen.getByText('Please enter a valid URL')).toBeInTheDocument();
      });

      expect(mockOnSubmit).not.toHaveBeenCalled();
    });
  });

  describe('form submission', () => {
    it('calls onSubmit with form data when valid', async () => {
      const user = userEvent.setup();
      render(<ProjectForm onSubmit={mockOnSubmit} />);

      await user.type(screen.getByLabelText('Project Name'), 'My New Project');
      await user.type(screen.getByLabelText('Site URL'), 'https://myproject.com');

      const form = screen.getByRole('button', { name: 'Create Project' }).closest('form')!;
      fireEvent.submit(form);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledTimes(1);
        // react-hook-form passes (data, event) - check first argument
        expect(mockOnSubmit.mock.calls[0][0]).toEqual({
          name: 'My New Project',
          site_url: 'https://myproject.com',
        });
      });
    });

    it('disables submit button when isSubmitting', () => {
      render(<ProjectForm onSubmit={mockOnSubmit} isSubmitting />);

      expect(screen.getByRole('button', { name: 'Saving...' })).toBeDisabled();
    });
  });
});
