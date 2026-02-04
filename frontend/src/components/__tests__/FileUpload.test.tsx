import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  FileUpload,
  type UploadedFile,
  MAX_FILE_SIZE_BYTES,
  ALLOWED_EXTENSIONS,
  ALLOWED_MIME_TYPES,
} from '../FileUpload';

// Helper to create a mock File
function createMockFile(
  name: string,
  size: number,
  type: string
): File {
  const content = new Array(size).fill('a').join('');
  return new File([content], name, { type });
}

// Helper to create a mock DataTransfer-like object for drag-drop testing
// jsdom doesn't support DataTransfer, so we mock the necessary interface
function createMockDataTransfer(files: File[]) {
  return {
    files,
    items: files.map((file) => ({ kind: 'file', type: file.type, getAsFile: () => file })),
  };
}

describe('FileUpload', () => {
  const mockOnFilesSelected = vi.fn();
  const mockOnFileRemove = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the drop zone with instructions', () => {
      render(<FileUpload />);

      expect(screen.getByText('Drag and drop files here')).toBeInTheDocument();
      expect(screen.getByText('or')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Browse files' })).toBeInTheDocument();
    });

    it('renders accepted file types information', () => {
      render(<FileUpload />);

      expect(screen.getByText(/PDF, DOCX, or TXT/)).toBeInTheDocument();
      expect(screen.getByText(/10 MB/)).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      const { container } = render(<FileUpload className="custom-class" />);

      expect(container.firstChild).toHaveClass('custom-class');
    });

    it('renders disabled state with reduced opacity', () => {
      render(<FileUpload disabled />);

      const browseButton = screen.getByRole('button', { name: 'Browse files' });
      expect(browseButton).toBeDisabled();
    });
  });

  describe('file input (browse)', () => {
    it('opens file dialog when Browse files button is clicked', async () => {
      const user = userEvent.setup();
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const clickSpy = vi.spyOn(fileInput, 'click');

      await user.click(screen.getByRole('button', { name: 'Browse files' }));

      expect(clickSpy).toHaveBeenCalled();
    });

    it('accepts multiple files', () => {
      render(<FileUpload />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(fileInput).toHaveAttribute('multiple');
    });

    it('has correct accept attribute for allowed file types', () => {
      render(<FileUpload />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(fileInput.accept).toBe(ALLOWED_EXTENSIONS.join(','));
    });

    it('calls onFilesSelected with valid files when selected via input', async () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const validFile = createMockFile('document.pdf', 1024, 'application/pdf');

      await waitFor(() => {
        fireEvent.change(fileInput, { target: { files: [validFile] } });
      });

      expect(mockOnFilesSelected).toHaveBeenCalledWith([validFile]);
    });

    it('resets file input value after selection to allow re-selecting same file', async () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const validFile = createMockFile('document.pdf', 1024, 'application/pdf');

      fireEvent.change(fileInput, { target: { files: [validFile] } });

      expect(fileInput.value).toBe('');
    });
  });

  describe('drag and drop', () => {
    it('shows visual feedback when dragging over drop zone', () => {
      render(<FileUpload />);

      const dropZone = screen.getByText('Drag and drop files here').closest('div')!;

      fireEvent.dragEnter(dropZone, {
        dataTransfer: { items: [{}] },
      });

      expect(screen.getByText('Drop files here')).toBeInTheDocument();
    });

    it('removes visual feedback when drag leaves', () => {
      render(<FileUpload />);

      const dropZone = screen.getByText('Drag and drop files here').closest('div')!;

      fireEvent.dragEnter(dropZone, { dataTransfer: { items: [{}] } });
      fireEvent.dragLeave(dropZone);

      expect(screen.getByText('Drag and drop files here')).toBeInTheDocument();
    });

    it('calls onFilesSelected when valid files are dropped', async () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const dropZone = screen.getByText('Drag and drop files here').closest('div')!;
      const validFile = createMockFile('document.pdf', 1024, 'application/pdf');
      const dataTransfer = createMockDataTransfer([validFile]);

      fireEvent.drop(dropZone, { dataTransfer });

      expect(mockOnFilesSelected).toHaveBeenCalledWith([validFile]);
    });

    it('does not process dropped files when disabled', () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} disabled />);

      const dropZone = screen.getByText('Drag and drop files here').closest('div')!;
      const validFile = createMockFile('document.pdf', 1024, 'application/pdf');
      const dataTransfer = createMockDataTransfer([validFile]);

      fireEvent.drop(dropZone, { dataTransfer });

      expect(mockOnFilesSelected).not.toHaveBeenCalled();
    });

    it('resets isDragging state on drop', () => {
      render(<FileUpload />);

      const dropZone = screen.getByText('Drag and drop files here').closest('div')!;
      const validFile = createMockFile('document.pdf', 1024, 'application/pdf');
      const dataTransfer = createMockDataTransfer([validFile]);

      fireEvent.dragEnter(dropZone, { dataTransfer: { items: [{}] } });
      expect(screen.getByText('Drop files here')).toBeInTheDocument();

      fireEvent.drop(dropZone, { dataTransfer });
      expect(screen.getByText('Drag and drop files here')).toBeInTheDocument();
    });
  });

  describe('file validation - size', () => {
    it('rejects files larger than MAX_FILE_SIZE_BYTES', () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const largeFile = createMockFile('large.pdf', MAX_FILE_SIZE_BYTES + 1, 'application/pdf');

      fireEvent.change(fileInput, { target: { files: [largeFile] } });

      expect(mockOnFilesSelected).not.toHaveBeenCalled();
      expect(screen.getByText('large.pdf')).toBeInTheDocument();
      expect(screen.getByText(/File exceeds maximum size/)).toBeInTheDocument();
    });

    it('accepts files exactly at MAX_FILE_SIZE_BYTES', () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const maxFile = createMockFile('max.pdf', MAX_FILE_SIZE_BYTES, 'application/pdf');

      fireEvent.change(fileInput, { target: { files: [maxFile] } });

      expect(mockOnFilesSelected).toHaveBeenCalledWith([maxFile]);
    });

    it('accepts files smaller than MAX_FILE_SIZE_BYTES', () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const smallFile = createMockFile('small.pdf', 1024, 'application/pdf');

      fireEvent.change(fileInput, { target: { files: [smallFile] } });

      expect(mockOnFilesSelected).toHaveBeenCalledWith([smallFile]);
    });
  });

  describe('file validation - type', () => {
    it('accepts PDF files by MIME type', () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const pdfFile = createMockFile('document.pdf', 1024, 'application/pdf');

      fireEvent.change(fileInput, { target: { files: [pdfFile] } });

      expect(mockOnFilesSelected).toHaveBeenCalledWith([pdfFile]);
    });

    it('accepts DOCX files by MIME type', () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const docxFile = createMockFile(
        'document.docx',
        1024,
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      );

      fireEvent.change(fileInput, { target: { files: [docxFile] } });

      expect(mockOnFilesSelected).toHaveBeenCalledWith([docxFile]);
    });

    it('accepts TXT files by MIME type', () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const txtFile = createMockFile('document.txt', 1024, 'text/plain');

      fireEvent.change(fileInput, { target: { files: [txtFile] } });

      expect(mockOnFilesSelected).toHaveBeenCalledWith([txtFile]);
    });

    it('accepts files by extension fallback when MIME type is not recognized', () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      // Some systems report empty or generic MIME types
      const pdfFile = createMockFile('document.pdf', 1024, '');

      fireEvent.change(fileInput, { target: { files: [pdfFile] } });

      expect(mockOnFilesSelected).toHaveBeenCalledWith([pdfFile]);
    });

    it('rejects unsupported file types', () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const imageFile = createMockFile('image.jpg', 1024, 'image/jpeg');

      fireEvent.change(fileInput, { target: { files: [imageFile] } });

      expect(mockOnFilesSelected).not.toHaveBeenCalled();
      expect(screen.getByText('image.jpg')).toBeInTheDocument();
      expect(screen.getByText(/Unsupported file type/)).toBeInTheDocument();
    });

    it('shows allowed extensions in error message for unsupported files', () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const imageFile = createMockFile('image.png', 1024, 'image/png');

      fireEvent.change(fileInput, { target: { files: [imageFile] } });

      expect(screen.getByText(/\.pdf, \.docx, \.txt/)).toBeInTheDocument();
    });
  });

  describe('file validation - mixed valid and invalid files', () => {
    it('accepts valid files and shows errors for invalid files', () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const validFile = createMockFile('valid.pdf', 1024, 'application/pdf');
      const invalidFile = createMockFile('invalid.jpg', 1024, 'image/jpeg');
      const tooLargeFile = createMockFile('large.pdf', MAX_FILE_SIZE_BYTES + 1, 'application/pdf');

      fireEvent.change(fileInput, { target: { files: [validFile, invalidFile, tooLargeFile] } });

      // Valid file should be passed to callback
      expect(mockOnFilesSelected).toHaveBeenCalledWith([validFile]);

      // Invalid files should show errors
      expect(screen.getByText('invalid.jpg')).toBeInTheDocument();
      expect(screen.getByText('large.pdf')).toBeInTheDocument();
    });
  });

  describe('validation errors display', () => {
    it('displays validation errors with file name and error message', () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const invalidFile = createMockFile('bad-file.exe', 1024, 'application/x-msdownload');

      fireEvent.change(fileInput, { target: { files: [invalidFile] } });

      expect(screen.getByText('bad-file.exe')).toBeInTheDocument();
      expect(screen.getByText(/Unsupported file type/)).toBeInTheDocument();
    });

    it('allows dismissing validation errors', async () => {
      const user = userEvent.setup();
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const invalidFile = createMockFile('bad-file.exe', 1024, 'application/x-msdownload');

      fireEvent.change(fileInput, { target: { files: [invalidFile] } });

      expect(screen.getByText('bad-file.exe')).toBeInTheDocument();

      const dismissButton = screen.getByRole('button', { name: /Dismiss error for bad-file.exe/ });
      await user.click(dismissButton);

      expect(screen.queryByText('bad-file.exe')).not.toBeInTheDocument();
    });

    it('clears previous validation errors when new files are selected', () => {
      render(<FileUpload onFilesSelected={mockOnFilesSelected} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

      // First invalid file
      const invalidFile1 = createMockFile('bad1.exe', 1024, 'application/x-msdownload');
      fireEvent.change(fileInput, { target: { files: [invalidFile1] } });
      expect(screen.getByText('bad1.exe')).toBeInTheDocument();

      // Second batch - should clear first error
      const invalidFile2 = createMockFile('bad2.exe', 1024, 'application/x-msdownload');
      fireEvent.change(fileInput, { target: { files: [invalidFile2] } });

      expect(screen.queryByText('bad1.exe')).not.toBeInTheDocument();
      expect(screen.getByText('bad2.exe')).toBeInTheDocument();
    });
  });

  describe('uploaded files list', () => {
    const uploadedFiles: UploadedFile[] = [
      { id: 'file-1', name: 'document.pdf', size: 1024, progress: 100, status: 'complete' },
      { id: 'file-2', name: 'uploading.docx', size: 2048, progress: 50, status: 'uploading' },
      { id: 'file-3', name: 'pending.txt', size: 512, progress: 0, status: 'pending' },
      { id: 'file-4', name: 'failed.pdf', size: 1024, progress: 30, status: 'error', error: 'Network error' },
    ];

    it('renders uploaded files list with file names and sizes', () => {
      render(<FileUpload uploadedFiles={uploadedFiles} />);

      expect(screen.getByText('document.pdf')).toBeInTheDocument();
      expect(screen.getByText('uploading.docx')).toBeInTheDocument();
      expect(screen.getByText('pending.txt')).toBeInTheDocument();
      expect(screen.getByText('failed.pdf')).toBeInTheDocument();

      // Check file sizes are formatted (multiple files may have same size display)
      const oneKBElements = screen.getAllByText('1 KB');
      expect(oneKBElements.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('2 KB')).toBeInTheDocument();
    });

    it('shows progress bar for uploading files', () => {
      render(<FileUpload uploadedFiles={[uploadedFiles[1]]} />);

      expect(screen.getByText('Uploading... 50%')).toBeInTheDocument();
    });

    it('shows "Ready" for pending files', () => {
      render(<FileUpload uploadedFiles={[uploadedFiles[2]]} />);

      expect(screen.getByText('Ready')).toBeInTheDocument();
    });

    it('shows "Uploaded" status for complete files', () => {
      render(<FileUpload uploadedFiles={[uploadedFiles[0]]} />);

      expect(screen.getByText('Uploaded')).toBeInTheDocument();
    });

    it('shows error message for failed files', () => {
      render(<FileUpload uploadedFiles={[uploadedFiles[3]]} />);

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('shows default error message when error is undefined', () => {
      const fileWithNoErrorMessage: UploadedFile = {
        id: 'file-5',
        name: 'failed.pdf',
        size: 1024,
        progress: 0,
        status: 'error',
      };
      render(<FileUpload uploadedFiles={[fileWithNoErrorMessage]} />);

      expect(screen.getByText('Upload failed')).toBeInTheDocument();
    });

    it('renders remove button when onFileRemove is provided', () => {
      render(
        <FileUpload
          uploadedFiles={[uploadedFiles[0]]}
          onFileRemove={mockOnFileRemove}
        />
      );

      expect(screen.getByRole('button', { name: /Remove document.pdf/ })).toBeInTheDocument();
    });

    it('does not render remove button when onFileRemove is not provided', () => {
      render(<FileUpload uploadedFiles={[uploadedFiles[0]]} />);

      expect(screen.queryByRole('button', { name: /Remove/ })).not.toBeInTheDocument();
    });

    it('calls onFileRemove with file id when remove button is clicked', async () => {
      const user = userEvent.setup();
      render(
        <FileUpload
          uploadedFiles={[uploadedFiles[0]]}
          onFileRemove={mockOnFileRemove}
        />
      );

      await user.click(screen.getByRole('button', { name: /Remove document.pdf/ }));

      expect(mockOnFileRemove).toHaveBeenCalledWith('file-1');
    });

    it('disables remove button while file is uploading', () => {
      render(
        <FileUpload
          uploadedFiles={[uploadedFiles[1]]}
          onFileRemove={mockOnFileRemove}
        />
      );

      expect(screen.getByRole('button', { name: /Remove uploading.docx/ })).toBeDisabled();
    });
  });

  describe('exported constants', () => {
    it('exports MAX_FILE_SIZE_BYTES as 10MB', () => {
      expect(MAX_FILE_SIZE_BYTES).toBe(10 * 1024 * 1024);
    });

    it('exports ALLOWED_EXTENSIONS with pdf, docx, txt', () => {
      expect(ALLOWED_EXTENSIONS).toEqual(['.pdf', '.docx', '.txt']);
    });

    it('exports ALLOWED_MIME_TYPES with correct MIME types', () => {
      expect(ALLOWED_MIME_TYPES).toContain('application/pdf');
      expect(ALLOWED_MIME_TYPES).toContain(
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      );
      expect(ALLOWED_MIME_TYPES).toContain('text/plain');
    });
  });
});
