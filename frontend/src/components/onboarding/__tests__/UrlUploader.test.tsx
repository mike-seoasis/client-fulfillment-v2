import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  UrlUploader,
  parseUrls,
  isValidUrl,
  normalizeUrl,
  getDomain,
  type ParsedUrl,
} from '../UrlUploader';
import { CsvDropzone, extractUrlsFromCsv } from '../CsvDropzone';
import { UrlPreviewList } from '../UrlPreviewList';

// ============================================================================
// Unit Tests: parseUrls function
// ============================================================================
describe('parseUrls', () => {
  describe('basic parsing', () => {
    it('parses URLs from newline-separated text', () => {
      const input = 'https://example.com\nhttps://test.com';
      const result = parseUrls(input);

      expect(result).toHaveLength(2);
      expect(result[0].url).toBe('https://example.com');
      expect(result[1].url).toBe('https://test.com');
    });

    it('trims whitespace from URLs', () => {
      const input = '  https://example.com  \n  https://test.com  ';
      const result = parseUrls(input);

      expect(result).toHaveLength(2);
      expect(result[0].url).toBe('https://example.com');
      expect(result[1].url).toBe('https://test.com');
    });

    it('filters out empty lines', () => {
      const input = 'https://example.com\n\n\nhttps://test.com\n';
      const result = parseUrls(input);

      expect(result).toHaveLength(2);
    });

    it('returns empty array for empty input', () => {
      expect(parseUrls('')).toHaveLength(0);
      expect(parseUrls('   ')).toHaveLength(0);
      expect(parseUrls('\n\n')).toHaveLength(0);
    });
  });

  describe('validation', () => {
    it('marks valid URLs with http protocol', () => {
      const result = parseUrls('http://example.com');
      expect(result[0].isValid).toBe(true);
    });

    it('marks valid URLs with https protocol', () => {
      const result = parseUrls('https://example.com');
      expect(result[0].isValid).toBe(true);
    });

    it('marks invalid URLs without protocol', () => {
      const result = parseUrls('example.com');
      expect(result[0].isValid).toBe(false);
    });

    it('marks invalid URLs with ftp protocol', () => {
      const result = parseUrls('ftp://example.com');
      expect(result[0].isValid).toBe(false);
    });

    it('marks invalid random text', () => {
      const result = parseUrls('not a url at all');
      expect(result[0].isValid).toBe(false);
    });

    it('validates mixed valid and invalid URLs', () => {
      const input = 'https://valid.com\ninvalid\nhttp://also-valid.com';
      const result = parseUrls(input);

      expect(result).toHaveLength(3);
      expect(result[0].isValid).toBe(true);
      expect(result[1].isValid).toBe(false);
      expect(result[2].isValid).toBe(true);
    });
  });

  describe('deduplication', () => {
    it('removes duplicate URLs', () => {
      const input = 'https://example.com\nhttps://example.com';
      const result = parseUrls(input);

      expect(result).toHaveLength(1);
      expect(result[0].url).toBe('https://example.com');
    });

    it('deduplicates by normalized URL (case-insensitive domain)', () => {
      const input = 'https://EXAMPLE.COM/page\nhttps://example.com/page';
      const result = parseUrls(input);

      expect(result).toHaveLength(1);
    });

    it('deduplicates URLs with different trailing slashes', () => {
      const input = 'https://example.com/page/\nhttps://example.com/page';
      const result = parseUrls(input);

      expect(result).toHaveLength(1);
    });

    it('keeps URLs with different paths as separate', () => {
      const input = 'https://example.com/page1\nhttps://example.com/page2';
      const result = parseUrls(input);

      expect(result).toHaveLength(2);
    });

    it('deduplicates invalid URLs by lowercased string', () => {
      const input = 'not-a-url\nNOT-A-URL\nNot-A-Url';
      const result = parseUrls(input);

      expect(result).toHaveLength(1);
    });
  });

  describe('normalization', () => {
    it('includes normalized URL in result', () => {
      const result = parseUrls('https://EXAMPLE.COM/Page');

      expect(result[0].normalizedUrl).toBe('https://example.com/Page');
    });

    it('preserves original URL in result', () => {
      const result = parseUrls('https://EXAMPLE.COM/Page');

      expect(result[0].url).toBe('https://EXAMPLE.COM/Page');
    });
  });
});

// ============================================================================
// Unit Tests: isValidUrl function
// ============================================================================
describe('isValidUrl', () => {
  it('returns true for https URLs', () => {
    expect(isValidUrl('https://example.com')).toBe(true);
    expect(isValidUrl('https://sub.domain.com/path')).toBe(true);
    expect(isValidUrl('https://example.com:8080/page')).toBe(true);
  });

  it('returns true for http URLs', () => {
    expect(isValidUrl('http://example.com')).toBe(true);
    expect(isValidUrl('http://localhost:3000')).toBe(true);
  });

  it('returns false for ftp URLs', () => {
    expect(isValidUrl('ftp://files.example.com')).toBe(false);
  });

  it('returns false for mailto URLs', () => {
    expect(isValidUrl('mailto:test@example.com')).toBe(false);
  });

  it('returns false for URLs without protocol', () => {
    expect(isValidUrl('example.com')).toBe(false);
    expect(isValidUrl('www.example.com')).toBe(false);
  });

  it('returns false for invalid strings', () => {
    expect(isValidUrl('')).toBe(false);
    expect(isValidUrl('not a url')).toBe(false);
    expect(isValidUrl('123')).toBe(false);
  });
});

// ============================================================================
// Unit Tests: normalizeUrl function
// ============================================================================
describe('normalizeUrl', () => {
  it('lowercases the domain', () => {
    expect(normalizeUrl('https://EXAMPLE.COM')).toBe('https://example.com/');
    expect(normalizeUrl('https://Example.Com/Path')).toBe('https://example.com/Path');
  });

  it('preserves path case (paths can be case-sensitive)', () => {
    expect(normalizeUrl('https://example.com/MyPage')).toBe('https://example.com/MyPage');
    expect(normalizeUrl('https://example.com/API/Users')).toBe('https://example.com/API/Users');
  });

  it('removes trailing slash except for root path', () => {
    expect(normalizeUrl('https://example.com/page/')).toBe('https://example.com/page');
    expect(normalizeUrl('https://example.com/')).toBe('https://example.com/');
  });

  it('preserves ports', () => {
    expect(normalizeUrl('https://example.com:8080/page')).toBe('https://example.com:8080/page');
  });

  it('preserves query parameters', () => {
    expect(normalizeUrl('https://example.com/page?foo=bar')).toBe('https://example.com/page?foo=bar');
  });

  it('preserves hash fragments', () => {
    expect(normalizeUrl('https://example.com/page#section')).toBe('https://example.com/page#section');
  });

  it('returns trimmed input for invalid URLs', () => {
    expect(normalizeUrl('  not-a-url  ')).toBe('not-a-url');
  });
});

// ============================================================================
// Unit Tests: getDomain function
// ============================================================================
describe('getDomain', () => {
  it('extracts domain from URL', () => {
    expect(getDomain('https://example.com/page')).toBe('example.com');
  });

  it('returns lowercase domain', () => {
    expect(getDomain('https://EXAMPLE.COM/page')).toBe('example.com');
  });

  it('includes subdomain', () => {
    expect(getDomain('https://www.example.com')).toBe('www.example.com');
    expect(getDomain('https://shop.example.com/products')).toBe('shop.example.com');
  });

  it('returns null for invalid URLs', () => {
    expect(getDomain('not-a-url')).toBeNull();
    expect(getDomain('')).toBeNull();
  });
});

// ============================================================================
// Unit Tests: extractUrlsFromCsv function
// ============================================================================
describe('extractUrlsFromCsv', () => {
  it('extracts URLs from "url" column (case-insensitive)', () => {
    const data = [
      { url: 'https://example1.com', name: 'Page 1' },
      { url: 'https://example2.com', name: 'Page 2' },
    ];
    const fields = ['url', 'name'];

    const result = extractUrlsFromCsv(data, fields);

    expect(result).toEqual(['https://example1.com', 'https://example2.com']);
  });

  it('handles uppercase "URL" column name', () => {
    const data = [
      { URL: 'https://example1.com', name: 'Page 1' },
    ];
    const fields = ['URL', 'name'];

    const result = extractUrlsFromCsv(data, fields);

    expect(result).toEqual(['https://example1.com']);
  });

  it('falls back to first column if no "url" column', () => {
    const data = [
      { link: 'https://example1.com', name: 'Page 1' },
      { link: 'https://example2.com', name: 'Page 2' },
    ];
    const fields = ['link', 'name'];

    const result = extractUrlsFromCsv(data, fields);

    expect(result).toEqual(['https://example1.com', 'https://example2.com']);
  });

  it('filters out empty values', () => {
    const data = [
      { url: 'https://example1.com' },
      { url: '' },
      { url: '  ' },
      { url: 'https://example2.com' },
    ];
    const fields = ['url'];

    const result = extractUrlsFromCsv(data, fields);

    expect(result).toEqual(['https://example1.com', 'https://example2.com']);
  });

  it('returns empty array for empty data', () => {
    expect(extractUrlsFromCsv([], ['url'])).toEqual([]);
  });

  it('returns empty array if no fields defined', () => {
    const data = [{ url: 'https://example.com' }];
    expect(extractUrlsFromCsv(data, undefined)).toEqual([]);
    expect(extractUrlsFromCsv(data, [])).toEqual([]);
  });
});

// ============================================================================
// Component Tests: UrlUploader
// ============================================================================
describe('UrlUploader Component', () => {
  const mockOnChange = vi.fn();
  const mockOnRawChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders textarea with placeholder', () => {
      render(<UrlUploader />);

      const textarea = screen.getByRole('textbox');
      expect(textarea).toBeInTheDocument();
      expect(textarea).toHaveAttribute('placeholder');
    });

    it('renders helper text', () => {
      render(<UrlUploader />);

      expect(screen.getByText(/Enter one URL per line/)).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<UrlUploader className="custom-class" />);

      expect(container.firstChild).toHaveClass('custom-class');
    });

    it('renders disabled state', () => {
      render(<UrlUploader disabled />);

      const textarea = screen.getByRole('textbox');
      expect(textarea).toBeDisabled();
    });
  });

  describe('URL parsing from textarea', () => {
    it('calls onChange with parsed URLs when text changes', async () => {
      const user = userEvent.setup();
      render(<UrlUploader onChange={mockOnChange} />);

      const textarea = screen.getByRole('textbox');
      await user.type(textarea, 'https://example.com');

      // onChange should be called with incremental typing, last call has full URL
      const lastCall = mockOnChange.mock.calls[mockOnChange.mock.calls.length - 1];
      expect(lastCall[0]).toEqual([
        expect.objectContaining({
          url: 'https://example.com',
          isValid: true,
        }),
      ]);
    });

    it('calls onRawChange with raw text', async () => {
      const user = userEvent.setup();
      render(<UrlUploader onRawChange={mockOnRawChange} />);

      const textarea = screen.getByRole('textbox');
      await user.type(textarea, 'test');

      expect(mockOnRawChange).toHaveBeenCalledWith('test');
    });

    it('parses multiple URLs on newlines', async () => {
      render(<UrlUploader onChange={mockOnChange} />);

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, {
        target: { value: 'https://example1.com\nhttps://example2.com' },
      });

      expect(mockOnChange).toHaveBeenCalledWith([
        expect.objectContaining({ url: 'https://example1.com', isValid: true }),
        expect.objectContaining({ url: 'https://example2.com', isValid: true }),
      ]);
    });

    it('re-parses on blur', async () => {
      render(<UrlUploader onChange={mockOnChange} />);

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'https://example.com' } });

      mockOnChange.mockClear();
      fireEvent.blur(textarea);

      expect(mockOnChange).toHaveBeenCalledTimes(1);
    });
  });
});

// ============================================================================
// Component Tests: CsvDropzone
// ============================================================================
describe('CsvDropzone Component', () => {
  const mockOnParsed = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders upload prompt', () => {
      render(<CsvDropzone onParsed={mockOnParsed} />);

      expect(screen.getByText('Click to upload')).toBeInTheDocument();
      expect(screen.getByText(/drag and drop/)).toBeInTheDocument();
      expect(screen.getByText('CSV files only')).toBeInTheDocument();
    });

    it('renders disabled state', () => {
      render(<CsvDropzone onParsed={mockOnParsed} disabled />);

      const dropzone = screen.getByRole('button', { name: /upload csv/i });
      expect(dropzone).toHaveClass('cursor-not-allowed');
    });
  });

  describe('drag and drop', () => {
    it('shows visual feedback when dragging over', () => {
      render(<CsvDropzone onParsed={mockOnParsed} />);

      const dropzone = screen.getByRole('button', { name: /upload csv/i });

      fireEvent.dragOver(dropzone);

      // Check that the dragging class is applied (border-palm-400)
      expect(dropzone).toHaveClass('border-palm-400');
    });

    it('removes visual feedback when drag leaves', () => {
      render(<CsvDropzone onParsed={mockOnParsed} />);

      const dropzone = screen.getByRole('button', { name: /upload csv/i });

      fireEvent.dragEnter(dropzone);
      fireEvent.dragLeave(dropzone);

      expect(dropzone).not.toHaveClass('border-palm-400');
    });
  });

  describe('file validation', () => {
    it('rejects non-CSV files', () => {
      render(<CsvDropzone onParsed={mockOnParsed} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const invalidFile = new File(['content'], 'image.png', { type: 'image/png' });

      fireEvent.change(fileInput, { target: { files: [invalidFile] } });

      expect(mockOnParsed).toHaveBeenCalledWith({
        urls: [],
        error: 'Invalid file type. Please upload a CSV file.',
        filename: 'image.png',
      });
    });

    it('accepts CSV files by MIME type', () => {
      render(<CsvDropzone onParsed={mockOnParsed} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(fileInput.accept).toContain('text/csv');
    });

    it('accepts CSV files by extension', () => {
      render(<CsvDropzone onParsed={mockOnParsed} />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(fileInput.accept).toContain('.csv');
    });
  });

  describe('keyboard accessibility', () => {
    it('activates on Enter key', () => {
      render(<CsvDropzone onParsed={mockOnParsed} />);

      const dropzone = screen.getByRole('button', { name: /upload csv/i });
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const clickSpy = vi.spyOn(fileInput, 'click');

      fireEvent.keyDown(dropzone, { key: 'Enter' });

      expect(clickSpy).toHaveBeenCalled();
    });

    it('activates on Space key', () => {
      render(<CsvDropzone onParsed={mockOnParsed} />);

      const dropzone = screen.getByRole('button', { name: /upload csv/i });
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const clickSpy = vi.spyOn(fileInput, 'click');

      fireEvent.keyDown(dropzone, { key: ' ' });

      expect(clickSpy).toHaveBeenCalled();
    });
  });
});

// ============================================================================
// Component Tests: UrlPreviewList
// ============================================================================
describe('UrlPreviewList Component', () => {
  const mockOnRemove = vi.fn();

  const validUrls: ParsedUrl[] = [
    { url: 'https://example1.com', normalizedUrl: 'https://example1.com/', isValid: true },
    { url: 'https://example2.com', normalizedUrl: 'https://example2.com/', isValid: true },
  ];

  const mixedUrls: ParsedUrl[] = [
    { url: 'https://valid.com', normalizedUrl: 'https://valid.com/', isValid: true },
    { url: 'invalid-url', normalizedUrl: 'invalid-url', isValid: false },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders empty state when no URLs', () => {
      render(<UrlPreviewList urls={[]} onRemove={mockOnRemove} />);

      expect(screen.getByText(/Enter URLs above/)).toBeInTheDocument();
    });

    it('renders URL count summary', () => {
      render(<UrlPreviewList urls={validUrls} onRemove={mockOnRemove} />);

      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText(/URLs to process/)).toBeInTheDocument();
    });

    it('renders total count', () => {
      render(<UrlPreviewList urls={validUrls} onRemove={mockOnRemove} />);

      expect(screen.getByText('2 total')).toBeInTheDocument();
    });

    it('shows invalid count when there are invalid URLs', () => {
      render(<UrlPreviewList urls={mixedUrls} onRemove={mockOnRemove} />);

      expect(screen.getByText('(1 invalid)')).toBeInTheDocument();
    });

    it('shows singular "URL" for single valid URL', () => {
      render(<UrlPreviewList urls={[validUrls[0]]} onRemove={mockOnRemove} />);

      expect(screen.getByText('URL to process')).toBeInTheDocument();
    });
  });

  describe('validation status display', () => {
    it('marks valid URLs with check icon', () => {
      render(<UrlPreviewList urls={validUrls} onRemove={mockOnRemove} />);

      // Valid URLs have bg-palm-100 circle
      const validIndicators = document.querySelectorAll('.bg-palm-100');
      expect(validIndicators).toHaveLength(2);
    });

    it('marks invalid URLs with X icon and "invalid" badge', () => {
      render(<UrlPreviewList urls={mixedUrls} onRemove={mockOnRemove} />);

      expect(screen.getByText('invalid')).toBeInTheDocument();
      // Invalid URLs have bg-coral-100 circle indicator (rounded-full)
      const invalidIndicators = document.querySelectorAll('.bg-coral-100.rounded-full');
      expect(invalidIndicators).toHaveLength(1);
    });

    it('shows invalid URLs with coral background', () => {
      render(<UrlPreviewList urls={mixedUrls} onRemove={mockOnRemove} />);

      const invalidRow = screen.getByText('invalid-url').closest('div');
      expect(invalidRow?.parentElement).toHaveClass('bg-coral-50');
    });
  });

  describe('remove functionality', () => {
    it('renders remove button for each URL', () => {
      render(<UrlPreviewList urls={validUrls} onRemove={mockOnRemove} />);

      const removeButtons = screen.getAllByRole('button', { name: /remove/i });
      expect(removeButtons).toHaveLength(2);
    });

    it('calls onRemove with normalizedUrl when remove button clicked', async () => {
      const user = userEvent.setup();
      render(<UrlPreviewList urls={validUrls} onRemove={mockOnRemove} />);

      const removeButton = screen.getByRole('button', { name: /remove https:\/\/example1.com/i });
      await user.click(removeButton);

      expect(mockOnRemove).toHaveBeenCalledWith('https://example1.com/');
    });

    it('has accessible label on remove button', () => {
      render(<UrlPreviewList urls={validUrls} onRemove={mockOnRemove} />);

      const removeButton = screen.getByRole('button', { name: /remove https:\/\/example1.com/i });
      expect(removeButton).toHaveAttribute('aria-label', 'Remove https://example1.com');
    });
  });
});
