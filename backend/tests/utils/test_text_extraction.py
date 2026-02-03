"""Tests for text extraction utilities.

Tests all extraction functions for PDF, DOCX, and TXT files:
- extract_text_from_pdf
- extract_text_from_docx
- extract_text_from_txt
- extract_text (main dispatcher)
- Text truncation at MAX_TEXT_LENGTH
- Unsupported content type handling
"""

import zipfile
from io import BytesIO

import pytest

from app.utils.text_extraction import (
    MAX_TEXT_LENGTH,
    TextExtractionError,
    UnsupportedFileTypeError,
    extract_text,
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_txt,
)

# ---------------------------------------------------------------------------
# Test Fixture Helpers
# ---------------------------------------------------------------------------


def create_sample_pdf(text: str = "Sample PDF content for testing.") -> bytes:
    """Create a minimal valid PDF with extractable text.

    This creates a proper PDF with a text stream that pypdf can extract.
    """
    # PDF with a simple text content stream
    stream_content = f"BT /F1 12 Tf 100 700 Td ({text}) Tj ET".encode("latin-1")
    stream_length = len(stream_content)

    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length """ + str(stream_length).encode() + b""" >>
stream
""" + stream_content + b"""
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
500
%%EOF"""
    return pdf_content


def create_sample_docx(text: str = "Sample DOCX content for testing.") -> bytes:
    """Create a minimal valid DOCX file with extractable text.

    DOCX is a ZIP archive containing XML files.
    """
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Content types
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        # Relationships
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            "</Relationships>",
        )
        # Document content with paragraph
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>"
            "</w:document>",
        )
    return buffer.getvalue()


def create_sample_docx_multiline(paragraphs: list[str]) -> bytes:
    """Create a DOCX with multiple paragraphs."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            "</Relationships>",
        )
        # Multiple paragraphs
        para_xml = "".join(
            f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs
        )
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{para_xml}</w:body>"
            "</w:document>",
        )
    return buffer.getvalue()


def create_sample_txt(text: str = "Sample text content for testing.") -> bytes:
    """Create UTF-8 encoded text content."""
    return text.encode("utf-8")


# ---------------------------------------------------------------------------
# PDF Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractTextFromPdf:
    """Tests for extract_text_from_pdf function."""

    def test_extract_basic_text(self) -> None:
        """Should extract text from a valid PDF."""
        pdf_bytes = create_sample_pdf("Hello world from PDF")
        result = extract_text_from_pdf(pdf_bytes)

        assert "Hello world from PDF" in result

    def test_extract_empty_pdf(self) -> None:
        """Should return empty string for PDF with no text."""
        # Minimal PDF with no content stream
        empty_pdf = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
200
%%EOF"""
        result = extract_text_from_pdf(empty_pdf)

        assert result == ""

    def test_extract_invalid_pdf_raises_error(self) -> None:
        """Should raise TextExtractionError for invalid PDF."""
        invalid_pdf = b"This is not a PDF file"

        with pytest.raises(TextExtractionError) as exc_info:
            extract_text_from_pdf(invalid_pdf)

        assert "Failed to extract text from PDF" in str(exc_info.value)

    def test_extract_corrupted_pdf_raises_error(self) -> None:
        """Should raise TextExtractionError for corrupted PDF."""
        corrupted_pdf = b"%PDF-1.4\ngarbage content here"

        with pytest.raises(TextExtractionError) as exc_info:
            extract_text_from_pdf(corrupted_pdf)

        assert "Failed to extract text from PDF" in str(exc_info.value)


# ---------------------------------------------------------------------------
# DOCX Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractTextFromDocx:
    """Tests for extract_text_from_docx function."""

    def test_extract_basic_text(self) -> None:
        """Should extract text from a valid DOCX."""
        docx_bytes = create_sample_docx("Hello world from DOCX")
        result = extract_text_from_docx(docx_bytes)

        assert result == "Hello world from DOCX"

    def test_extract_multiple_paragraphs(self) -> None:
        """Should extract all paragraphs joined by double newlines."""
        paragraphs = ["First paragraph", "Second paragraph", "Third paragraph"]
        docx_bytes = create_sample_docx_multiline(paragraphs)
        result = extract_text_from_docx(docx_bytes)

        assert "First paragraph" in result
        assert "Second paragraph" in result
        assert "Third paragraph" in result
        # Paragraphs should be separated
        assert "\n\n" in result

    def test_extract_empty_docx(self) -> None:
        """Should return empty string for DOCX with no text."""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                "</Types>",
            )
            zf.writestr(
                "_rels/.rels",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="word/document.xml"/>'
                "</Relationships>",
            )
            # Empty body
            zf.writestr(
                "word/document.xml",
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body></w:body>"
                "</w:document>",
            )

        result = extract_text_from_docx(buffer.getvalue())
        assert result == ""

    def test_extract_invalid_docx_raises_error(self) -> None:
        """Should raise TextExtractionError for invalid DOCX."""
        invalid_docx = b"This is not a DOCX file"

        with pytest.raises(TextExtractionError) as exc_info:
            extract_text_from_docx(invalid_docx)

        assert "Failed to extract text from DOCX" in str(exc_info.value)

    def test_extract_corrupted_zip_raises_error(self) -> None:
        """Should raise TextExtractionError for corrupted ZIP archive."""
        # Start of a ZIP but truncated
        corrupted_docx = b"PK\x03\x04corrupted content"

        with pytest.raises(TextExtractionError) as exc_info:
            extract_text_from_docx(corrupted_docx)

        assert "Failed to extract text from DOCX" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TXT Extraction Tests
# ---------------------------------------------------------------------------


class TestExtractTextFromTxt:
    """Tests for extract_text_from_txt function."""

    def test_extract_utf8_text(self) -> None:
        """Should extract UTF-8 encoded text."""
        text = "Hello world with UTF-8: café résumé"
        txt_bytes = text.encode("utf-8")
        result = extract_text_from_txt(txt_bytes)

        assert result == text

    def test_extract_ascii_text(self) -> None:
        """Should extract ASCII text."""
        text = "Simple ASCII text content"
        txt_bytes = text.encode("ascii")
        result = extract_text_from_txt(txt_bytes)

        assert result == text

    def test_extract_multiline_text(self) -> None:
        """Should preserve line breaks."""
        text = "Line one\nLine two\nLine three"
        txt_bytes = text.encode("utf-8")
        result = extract_text_from_txt(txt_bytes)

        assert result == text

    def test_extract_latin1_fallback(self) -> None:
        """Should fall back to latin-1 for non-UTF8 content."""
        # Latin-1 encoded text with characters invalid in UTF-8
        latin1_text = "Text with special chars: \xe9\xe0\xfc"  # éàü in latin-1
        txt_bytes = latin1_text.encode("latin-1")
        result = extract_text_from_txt(txt_bytes)

        # Should decode successfully via latin-1 fallback
        assert result == latin1_text

    def test_extract_empty_text(self) -> None:
        """Should return empty string for empty file."""
        txt_bytes = b""
        result = extract_text_from_txt(txt_bytes)

        assert result == ""


# ---------------------------------------------------------------------------
# Main Dispatcher Tests
# ---------------------------------------------------------------------------


class TestExtractText:
    """Tests for the main extract_text dispatcher function."""

    def test_dispatch_pdf(self) -> None:
        """Should route PDF content type to PDF extractor."""
        pdf_bytes = create_sample_pdf("PDF content")
        result = extract_text(pdf_bytes, "application/pdf")

        assert "PDF content" in result

    def test_dispatch_docx(self) -> None:
        """Should route DOCX content type to DOCX extractor."""
        docx_bytes = create_sample_docx("DOCX content")
        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        result = extract_text(docx_bytes, content_type)

        assert result == "DOCX content"

    def test_dispatch_txt(self) -> None:
        """Should route text/plain content type to TXT extractor."""
        txt_bytes = create_sample_txt("Plain text content")
        result = extract_text(txt_bytes, "text/plain")

        assert result == "Plain text content"

    def test_normalize_content_type_with_charset(self) -> None:
        """Should handle content type with charset parameter."""
        txt_bytes = create_sample_txt("Text with charset")
        # Content type with charset parameter
        result = extract_text(txt_bytes, "text/plain; charset=utf-8")

        assert result == "Text with charset"

    def test_normalize_content_type_case_insensitive(self) -> None:
        """Should handle content type case-insensitively."""
        txt_bytes = create_sample_txt("Case test")
        result = extract_text(txt_bytes, "TEXT/PLAIN")

        assert result == "Case test"

    def test_unsupported_content_type_raises_error(self) -> None:
        """Should raise UnsupportedFileTypeError for unknown types."""
        file_bytes = b"some content"

        with pytest.raises(UnsupportedFileTypeError) as exc_info:
            extract_text(file_bytes, "image/png")

        assert "Unsupported file type: image/png" in str(exc_info.value)
        assert "application/pdf" in str(exc_info.value)  # Shows supported types

    def test_unsupported_content_type_json(self) -> None:
        """Should raise UnsupportedFileTypeError for JSON files."""
        json_bytes = b'{"key": "value"}'

        with pytest.raises(UnsupportedFileTypeError) as exc_info:
            extract_text(json_bytes, "application/json")

        assert "Unsupported file type: application/json" in str(exc_info.value)

    def test_unsupported_content_type_html(self) -> None:
        """Should raise UnsupportedFileTypeError for HTML files."""
        html_bytes = b"<html><body>Hello</body></html>"

        with pytest.raises(UnsupportedFileTypeError) as exc_info:
            extract_text(html_bytes, "text/html")

        assert "Unsupported file type: text/html" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Text Truncation Tests
# ---------------------------------------------------------------------------


class TestTextTruncation:
    """Tests for text truncation at MAX_TEXT_LENGTH."""

    def test_short_text_not_truncated(self) -> None:
        """Should not truncate text under the limit."""
        short_text = "Short content"
        txt_bytes = create_sample_txt(short_text)
        result = extract_text(txt_bytes, "text/plain")

        assert result == short_text

    def test_exact_limit_not_truncated(self) -> None:
        """Should not truncate text at exactly the limit."""
        exact_text = "x" * MAX_TEXT_LENGTH
        txt_bytes = create_sample_txt(exact_text)
        result = extract_text(txt_bytes, "text/plain")

        assert len(result) == MAX_TEXT_LENGTH
        assert result == exact_text

    def test_long_text_truncated(self) -> None:
        """Should truncate text exceeding MAX_TEXT_LENGTH."""
        # Create text that's 10 characters over the limit
        long_text = "x" * (MAX_TEXT_LENGTH + 10)
        txt_bytes = create_sample_txt(long_text)
        result = extract_text(txt_bytes, "text/plain")

        assert len(result) == MAX_TEXT_LENGTH
        assert result == "x" * MAX_TEXT_LENGTH

    def test_truncation_preserves_beginning(self) -> None:
        """Should preserve the beginning of text when truncating."""
        # Create recognizable text at the start
        start_text = "START_MARKER_"
        long_text = start_text + "x" * MAX_TEXT_LENGTH
        txt_bytes = create_sample_txt(long_text)
        result = extract_text(txt_bytes, "text/plain")

        assert result.startswith(start_text)
        assert len(result) == MAX_TEXT_LENGTH

    def test_max_text_length_constant(self) -> None:
        """Verify MAX_TEXT_LENGTH is 100k as specified."""
        assert MAX_TEXT_LENGTH == 100_000
