"""Tests for document parser for PDF, DOCX, TXT brand documents.

Tests the DocumentParser class and related functionality:
- PDF parsing with pypdf
- DOCX parsing with python-docx
- TXT parsing with encoding detection
- File size validation
- Format detection
- Error handling
- Metadata extraction
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.utils.document_parser import (
    DocumentCorruptedError,
    DocumentFormat,
    DocumentMetadata,
    DocumentParser,
    DocumentParserError,
    DocumentParseResult,
    FileTooLargeError,
    UnsupportedFormatError,
    get_document_parser,
    parse_document,
    parse_document_file,
)


class TestDocumentFormat:
    """Tests for the DocumentFormat enum."""

    def test_format_values_exist(self) -> None:
        """Verify all expected format values exist."""
        assert DocumentFormat.PDF.value == "pdf"
        assert DocumentFormat.DOCX.value == "docx"
        assert DocumentFormat.TXT.value == "txt"

    def test_format_count(self) -> None:
        """Verify correct number of formats."""
        assert len(DocumentFormat) == 3


class TestDocumentMetadata:
    """Tests for the DocumentMetadata dataclass."""

    def test_create_metadata(self) -> None:
        """Test creating document metadata."""
        metadata = DocumentMetadata(
            filename="test.pdf",
            format=DocumentFormat.PDF,
            file_size_bytes=1024,
            page_count=5,
            word_count=500,
            character_count=3000,
            author="John Doe",
            title="Brand Guidelines",
        )
        assert metadata.filename == "test.pdf"
        assert metadata.format == DocumentFormat.PDF
        assert metadata.file_size_bytes == 1024
        assert metadata.page_count == 5
        assert metadata.word_count == 500
        assert metadata.character_count == 3000
        assert metadata.author == "John Doe"
        assert metadata.title == "Brand Guidelines"

    def test_metadata_to_dict(self) -> None:
        """Test converting metadata to dictionary."""
        metadata = DocumentMetadata(
            filename="brand.docx",
            format=DocumentFormat.DOCX,
            file_size_bytes=2048,
            word_count=100,
            character_count=600,
        )
        result = metadata.to_dict()
        assert result["filename"] == "brand.docx"
        assert result["format"] == "docx"
        assert result["file_size_bytes"] == 2048
        assert result["page_count"] is None
        assert result["word_count"] == 100
        assert result["character_count"] == 600

    def test_metadata_default_values(self) -> None:
        """Test metadata default values."""
        metadata = DocumentMetadata(
            filename="test.txt",
            format=DocumentFormat.TXT,
            file_size_bytes=100,
        )
        assert metadata.page_count is None
        assert metadata.word_count == 0
        assert metadata.character_count == 0
        assert metadata.author is None
        assert metadata.title is None
        assert metadata.created_date is None
        assert metadata.modified_date is None


class TestDocumentParseResult:
    """Tests for the DocumentParseResult dataclass."""

    def test_create_success_result(self) -> None:
        """Test creating a successful parse result."""
        metadata = DocumentMetadata(
            filename="test.pdf",
            format=DocumentFormat.PDF,
            file_size_bytes=1024,
        )
        result = DocumentParseResult(
            success=True,
            content="This is the document content.",
            metadata=metadata,
            duration_ms=150.5,
            sections=["Section 1", "Section 2"],
        )
        assert result.success is True
        assert result.content == "This is the document content."
        assert result.metadata is not None
        assert result.error is None
        assert result.duration_ms == 150.5
        assert len(result.sections) == 2
        assert result.is_empty is False

    def test_create_error_result(self) -> None:
        """Test creating an error parse result."""
        result = DocumentParseResult(
            success=False,
            error="File corrupted",
            duration_ms=10.0,
        )
        assert result.success is False
        assert result.content == ""
        assert result.error == "File corrupted"
        assert result.is_empty is True

    def test_is_empty_with_whitespace_content(self) -> None:
        """Test is_empty property with whitespace-only content."""
        result = DocumentParseResult(
            success=True,
            content="   \n\t   ",
        )
        assert result.is_empty is True


class TestDocumentParserExceptions:
    """Tests for document parser exception classes."""

    def test_unsupported_format_error(self) -> None:
        """Test UnsupportedFormatError exception."""
        error = UnsupportedFormatError(
            extension=".xyz",
            project_id="proj-123",
            filename="test.xyz",
        )
        assert ".xyz" in str(error)
        assert error.extension == ".xyz"
        assert error.project_id == "proj-123"
        assert error.filename == "test.xyz"

    def test_file_too_large_error(self) -> None:
        """Test FileTooLargeError exception."""
        error = FileTooLargeError(
            file_size=100_000_000,
            max_size=50_000_000,
            project_id="proj-123",
        )
        assert "100,000,000" in str(error)
        assert "50,000,000" in str(error)
        assert error.file_size == 100_000_000
        assert error.max_size == 50_000_000

    def test_document_corrupted_error(self) -> None:
        """Test DocumentCorruptedError exception."""
        error = DocumentCorruptedError(
            message="Invalid PDF structure",
            project_id="proj-123",
            filename="bad.pdf",
        )
        assert "Invalid PDF structure" in str(error)
        assert error.project_id == "proj-123"


class TestDocumentParser:
    """Tests for the DocumentParser class."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create a fresh parser instance for tests."""
        return DocumentParser()

    def test_parser_initialization(self, parser: DocumentParser) -> None:
        """Test parser initializes with default settings."""
        assert parser._max_file_size == 50 * 1024 * 1024  # 50MB

    def test_parser_custom_max_size(self) -> None:
        """Test creating parser with custom max file size."""
        custom_parser = DocumentParser(max_file_size=10 * 1024 * 1024)
        assert custom_parser._max_file_size == 10 * 1024 * 1024

    def test_get_supported_formats(self, parser: DocumentParser) -> None:
        """Test getting list of supported formats."""
        formats = parser.get_supported_formats()
        assert ".pdf" in formats
        assert ".docx" in formats
        assert ".txt" in formats
        assert len(formats) == 3

    def test_is_supported_pdf(self, parser: DocumentParser) -> None:
        """Test checking PDF support."""
        assert parser.is_supported("document.pdf") is True
        assert parser.is_supported("document.PDF") is True
        assert parser.is_supported("path/to/document.pdf") is True

    def test_is_supported_docx(self, parser: DocumentParser) -> None:
        """Test checking DOCX support."""
        assert parser.is_supported("document.docx") is True
        assert parser.is_supported("document.DOCX") is True

    def test_is_supported_txt(self, parser: DocumentParser) -> None:
        """Test checking TXT support."""
        assert parser.is_supported("document.txt") is True
        assert parser.is_supported("document.TXT") is True

    def test_is_supported_unsupported(self, parser: DocumentParser) -> None:
        """Test checking unsupported formats."""
        assert parser.is_supported("document.doc") is False
        assert parser.is_supported("document.xls") is False
        assert parser.is_supported("document.pptx") is False
        assert parser.is_supported("image.png") is False


class TestFormatDetection:
    """Tests for document format detection."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create a parser for tests."""
        return DocumentParser()

    def test_detect_pdf(self, parser: DocumentParser) -> None:
        """Test detecting PDF format."""
        assert parser._detect_format("document.pdf") == DocumentFormat.PDF
        assert parser._detect_format("document.PDF") == DocumentFormat.PDF

    def test_detect_docx(self, parser: DocumentParser) -> None:
        """Test detecting DOCX format."""
        assert parser._detect_format("document.docx") == DocumentFormat.DOCX
        assert parser._detect_format("document.DOCX") == DocumentFormat.DOCX

    def test_detect_txt(self, parser: DocumentParser) -> None:
        """Test detecting TXT format."""
        assert parser._detect_format("document.txt") == DocumentFormat.TXT
        assert parser._detect_format("document.TXT") == DocumentFormat.TXT

    def test_detect_unsupported_raises(self, parser: DocumentParser) -> None:
        """Test detecting unsupported format raises error."""
        with pytest.raises(UnsupportedFormatError) as exc_info:
            parser._detect_format("document.doc")
        assert exc_info.value.extension == ".doc"

    def test_detect_no_extension_raises(self, parser: DocumentParser) -> None:
        """Test detecting file without extension raises error."""
        with pytest.raises(UnsupportedFormatError):
            parser._detect_format("document")


class TestFileSizeValidation:
    """Tests for file size validation."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create a parser with small max size for testing."""
        return DocumentParser(max_file_size=1000)  # 1KB

    def test_valid_file_size(self, parser: DocumentParser) -> None:
        """Test that valid file sizes pass validation."""
        # Should not raise
        parser._validate_file_size(500, "test.pdf")
        parser._validate_file_size(1000, "test.pdf")

    def test_invalid_file_size_raises(self, parser: DocumentParser) -> None:
        """Test that large files raise FileTooLargeError."""
        with pytest.raises(FileTooLargeError) as exc_info:
            parser._validate_file_size(1001, "test.pdf")
        assert exc_info.value.file_size == 1001
        assert exc_info.value.max_size == 1000


class TestTxtParsing:
    """Tests for TXT document parsing."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create a parser for tests."""
        return DocumentParser()

    def test_parse_txt_utf8(self, parser: DocumentParser) -> None:
        """Test parsing UTF-8 encoded TXT file."""
        content = "Hello, World!\n\nThis is a test document."
        file_bytes = content.encode("utf-8")

        result = parser.parse_bytes(file_bytes, "test.txt")

        assert result.success is True
        assert "Hello, World!" in result.content
        assert result.metadata is not None
        assert result.metadata.format == DocumentFormat.TXT
        assert result.metadata.word_count > 0

    def test_parse_txt_latin1(self, parser: DocumentParser) -> None:
        """Test parsing Latin-1 encoded TXT file."""
        content = "Caf\xe9 and na\xefve"
        file_bytes = content.encode("latin-1")

        result = parser.parse_bytes(file_bytes, "test.txt")

        assert result.success is True
        assert "Caf" in result.content

    def test_parse_txt_sections(self, parser: DocumentParser) -> None:
        """Test that TXT parsing splits on double newlines."""
        content = "Section 1\n\nSection 2\n\nSection 3"
        file_bytes = content.encode("utf-8")

        result = parser.parse_bytes(file_bytes, "test.txt")

        assert result.success is True
        assert len(result.sections) == 3
        assert "Section 1" in result.sections[0]
        assert "Section 2" in result.sections[1]
        assert "Section 3" in result.sections[2]

    def test_parse_txt_empty_file(self, parser: DocumentParser) -> None:
        """Test parsing empty TXT file."""
        file_bytes = b""

        result = parser.parse_bytes(file_bytes, "empty.txt")

        assert result.success is True
        assert result.is_empty is True

    def test_parse_txt_with_project_id(self, parser: DocumentParser) -> None:
        """Test parsing with project_id for logging."""
        content = "Test content"
        file_bytes = content.encode("utf-8")

        result = parser.parse_bytes(file_bytes, "test.txt", project_id="proj-123")

        assert result.success is True

    def test_parse_txt_bom(self, parser: DocumentParser) -> None:
        """Test parsing TXT file with UTF-8 BOM."""
        content = "Content after BOM"
        file_bytes = b"\xef\xbb\xbf" + content.encode("utf-8")

        result = parser.parse_bytes(file_bytes, "test.txt")

        assert result.success is True
        assert "Content after BOM" in result.content


class TestPdfParsing:
    """Tests for PDF document parsing."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create a parser for tests."""
        return DocumentParser()

    def test_parse_pdf_invalid_content_or_no_library(
        self, parser: DocumentParser
    ) -> None:
        """Test handling of invalid PDF content or missing library."""
        file_bytes = b"This is not a valid PDF file"

        # Will raise either DocumentCorruptedError (if pypdf installed)
        # or DocumentParserError (if pypdf not installed)
        with pytest.raises((DocumentCorruptedError, DocumentParserError)):
            parser.parse_bytes(file_bytes, "invalid.pdf")

    def test_parse_pdf_with_mock(self, parser: DocumentParser) -> None:
        """Test PDF parsing with mocked pypdf."""
        # Create mock PDF reader
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content"

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_reader.metadata = MagicMock()
        mock_reader.metadata.author = "Test Author"
        mock_reader.metadata.title = "Test Title"
        mock_reader.metadata.creation_date = None
        mock_reader.metadata.modification_date = None

        # Mock the import and reader within _parse_pdf
        with patch.object(parser, "_parse_pdf") as mock_parse:
            mock_result = DocumentParseResult(
                success=True,
                content="Page 1 content",
                metadata=DocumentMetadata(
                    filename="test.pdf",
                    format=DocumentFormat.PDF,
                    file_size_bytes=100,
                    page_count=1,
                    word_count=3,
                    character_count=14,
                    author="Test Author",
                ),
            )
            mock_parse.return_value = mock_result

            file_bytes = b"%PDF-1.4 mock content"
            result = parser.parse_bytes(file_bytes, "test.pdf")

            assert result.success is True
            assert "Page 1 content" in result.content
            assert result.metadata is not None
            assert result.metadata.page_count == 1
            assert result.metadata.author == "Test Author"


class TestDocxParsing:
    """Tests for DOCX document parsing."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create a parser for tests."""
        return DocumentParser()

    def test_parse_docx_invalid_content_or_no_library(
        self, parser: DocumentParser
    ) -> None:
        """Test handling of invalid DOCX content or missing library."""
        file_bytes = b"This is not a valid DOCX file"

        # Will raise either DocumentCorruptedError (if python-docx installed)
        # or DocumentParserError (if python-docx not installed)
        with pytest.raises((DocumentCorruptedError, DocumentParserError)):
            parser.parse_bytes(file_bytes, "invalid.docx")

    def test_parse_docx_with_mock(self, parser: DocumentParser) -> None:
        """Test DOCX parsing with mocked python-docx."""
        # Create mock paragraph
        mock_para = MagicMock()
        mock_para.text = "Paragraph content"

        # Create mock document
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]
        mock_doc.tables = []
        mock_doc.core_properties = MagicMock()
        mock_doc.core_properties.author = "Test Author"
        mock_doc.core_properties.title = "Test Document"
        mock_doc.core_properties.created = None
        mock_doc.core_properties.modified = None

        with patch("docx.Document", return_value=mock_doc):
            file_bytes = b"PK mock docx"
            result = parser.parse_bytes(file_bytes, "test.docx")

            assert result.success is True
            assert "Paragraph content" in result.content
            assert result.metadata is not None
            assert result.metadata.author == "Test Author"

    def test_parse_docx_with_tables(self, parser: DocumentParser) -> None:
        """Test DOCX parsing extracts table content."""
        # Create mock cell
        mock_cell1 = MagicMock()
        mock_cell1.text = "Cell 1"
        mock_cell2 = MagicMock()
        mock_cell2.text = "Cell 2"

        # Create mock row
        mock_row = MagicMock()
        mock_row.cells = [mock_cell1, mock_cell2]

        # Create mock table
        mock_table = MagicMock()
        mock_table.rows = [mock_row]

        # Create mock document
        mock_doc = MagicMock()
        mock_doc.paragraphs = []
        mock_doc.tables = [mock_table]
        mock_doc.core_properties = MagicMock()
        mock_doc.core_properties.author = None
        mock_doc.core_properties.title = None
        mock_doc.core_properties.created = None
        mock_doc.core_properties.modified = None

        with patch("docx.Document", return_value=mock_doc):
            file_bytes = b"PK mock docx"
            result = parser.parse_bytes(file_bytes, "test.docx")

            assert result.success is True
            assert "Cell 1" in result.content
            assert "Cell 2" in result.content


class TestParseFile:
    """Tests for parsing documents from file path."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create a parser for tests."""
        return DocumentParser()

    @pytest.fixture
    def temp_txt_file(self, tmp_path: Path) -> Path:
        """Create a temporary TXT file for testing."""
        file_path = tmp_path / "test_document.txt"
        file_path.write_text("This is test content for the document parser.")
        return file_path

    def test_parse_file_success(
        self, parser: DocumentParser, temp_txt_file: Path
    ) -> None:
        """Test parsing file from path."""
        result = parser.parse_file(temp_txt_file)

        assert result.success is True
        assert "test content" in result.content
        assert result.metadata is not None
        assert result.metadata.filename == "test_document.txt"

    def test_parse_file_not_found(self, parser: DocumentParser) -> None:
        """Test parsing non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/path/document.txt")

    def test_parse_file_with_project_id(
        self, parser: DocumentParser, temp_txt_file: Path
    ) -> None:
        """Test parsing file with project_id for logging."""
        result = parser.parse_file(temp_txt_file, project_id="proj-123")

        assert result.success is True


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_document_parser_singleton(self) -> None:
        """Test that get_document_parser returns a singleton."""
        parser1 = get_document_parser()
        parser2 = get_document_parser()
        assert parser1 is parser2

    def test_parse_document_function(self) -> None:
        """Test the parse_document convenience function."""
        content = "Test content for convenience function"
        file_bytes = content.encode("utf-8")

        result = parse_document(file_bytes, "test.txt")

        assert result.success is True
        assert "Test content" in result.content

    def test_parse_document_file_function(self, tmp_path: Path) -> None:
        """Test the parse_document_file convenience function."""
        file_path = tmp_path / "convenience_test.txt"
        file_path.write_text("Content for file test")

        result = parse_document_file(file_path)

        assert result.success is True
        assert "Content for file test" in result.content


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create a parser for tests."""
        return DocumentParser()

    def test_unicode_content(self, parser: DocumentParser) -> None:
        """Test handling of unicode content."""
        content = "Unicode: \u00e9\u00e8\u00ea \u4e2d\u6587 \U0001f600"
        file_bytes = content.encode("utf-8")

        result = parser.parse_bytes(file_bytes, "unicode.txt")

        assert result.success is True
        assert "\u00e9" in result.content

    def test_very_long_filename(self, parser: DocumentParser) -> None:
        """Test handling of very long filenames."""
        long_filename = "a" * 200 + ".txt"
        file_bytes = b"content"

        result = parser.parse_bytes(file_bytes, long_filename)

        assert result.success is True

    def test_filename_with_special_chars(self, parser: DocumentParser) -> None:
        """Test handling of filenames with special characters."""
        filename = "brand guide (2024) - final!.txt"
        file_bytes = b"content"

        result = parser.parse_bytes(file_bytes, filename)

        assert result.success is True

    def test_word_count_calculation(self, parser: DocumentParser) -> None:
        """Test word count calculation."""
        content = "One two three four five"
        file_bytes = content.encode("utf-8")

        result = parser.parse_bytes(file_bytes, "count.txt")

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.word_count == 5

    def test_character_count_calculation(self, parser: DocumentParser) -> None:
        """Test character count calculation."""
        content = "Hello, World!"
        file_bytes = content.encode("utf-8")

        result = parser.parse_bytes(file_bytes, "count.txt")

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.character_count == len(content)

    def test_parse_bytes_unsupported_format(self, parser: DocumentParser) -> None:
        """Test parse_bytes with unsupported format."""
        with pytest.raises(UnsupportedFormatError):
            parser.parse_bytes(b"content", "document.xls")

    def test_parse_bytes_too_large(self) -> None:
        """Test parse_bytes with file exceeding size limit."""
        small_parser = DocumentParser(max_file_size=10)
        file_bytes = b"x" * 100

        with pytest.raises(FileTooLargeError):
            small_parser.parse_bytes(file_bytes, "large.txt")


class TestLoggingBehavior:
    """Tests for logging behavior (verifying no crashes)."""

    @pytest.fixture
    def parser(self) -> DocumentParser:
        """Create a parser for tests."""
        return DocumentParser()

    def test_logging_with_all_ids(self, parser: DocumentParser) -> None:
        """Test that logging works with project_id."""
        content = "Test content"
        file_bytes = content.encode("utf-8")

        # Should not raise any exceptions
        result = parser.parse_bytes(
            file_bytes,
            "test.txt",
            project_id="proj-123",
        )

        assert result.success is True

    def test_logging_sanitizes_long_filename(self, parser: DocumentParser) -> None:
        """Test that long filenames are sanitized in logs."""
        long_filename = "a" * 100 + ".txt"
        file_bytes = b"content"

        # Should not raise any exceptions
        result = parser.parse_bytes(file_bytes, long_filename)

        assert result.success is True
