"""Text extraction utilities for processing uploaded documents.

This module provides functions to extract text from various document formats
including PDF, DOCX, and plain text files.
"""

import io
import logging

from docx import Document
from pypdf import PdfReader

logger = logging.getLogger(__name__)

# Maximum characters before truncation
MAX_TEXT_LENGTH = 100_000


class TextExtractionError(Exception):
    """Base exception for text extraction errors."""

    pass


class UnsupportedFileTypeError(TextExtractionError):
    """Raised when attempting to extract text from an unsupported file type."""

    pass


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text content from a PDF file.

    Args:
        file_bytes: Raw bytes of the PDF file.

    Returns:
        Extracted text content from all pages.

    Raises:
        TextExtractionError: If the PDF cannot be read or parsed.
    """
    try:
        pdf_file = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_file)

        text_parts: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        return "\n\n".join(text_parts)
    except Exception as e:
        raise TextExtractionError(f"Failed to extract text from PDF: {e}") from e


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text content from a DOCX file.

    Args:
        file_bytes: Raw bytes of the DOCX file.

    Returns:
        Extracted text content from all paragraphs.

    Raises:
        TextExtractionError: If the DOCX cannot be read or parsed.
    """
    try:
        docx_file = io.BytesIO(file_bytes)
        document = Document(docx_file)

        text_parts: list[str] = []
        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)

        return "\n\n".join(text_parts)
    except Exception as e:
        raise TextExtractionError(f"Failed to extract text from DOCX: {e}") from e


def extract_text_from_txt(file_bytes: bytes) -> str:
    """Extract text content from a plain text file.

    Args:
        file_bytes: Raw bytes of the text file.

    Returns:
        Decoded text content.

    Raises:
        TextExtractionError: If the text cannot be decoded.
    """
    try:
        # Try UTF-8 first, fall back to latin-1 which accepts any byte sequence
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1")
    except Exception as e:
        raise TextExtractionError(f"Failed to extract text from file: {e}") from e


def _truncate_text(text: str) -> str:
    """Truncate text to MAX_TEXT_LENGTH if necessary.

    Args:
        text: The text to potentially truncate.

    Returns:
        Original text if under limit, truncated text otherwise.
    """
    if len(text) <= MAX_TEXT_LENGTH:
        return text

    logger.warning(
        "Extracted text truncated from %d to %d characters",
        len(text),
        MAX_TEXT_LENGTH,
    )
    return text[:MAX_TEXT_LENGTH]


def extract_text(file_bytes: bytes, content_type: str) -> str:
    """Extract text from a file based on its content type.

    This is the main dispatcher function that routes extraction to the
    appropriate handler based on the file's MIME type.

    Args:
        file_bytes: Raw bytes of the file.
        content_type: MIME type of the file (e.g., 'application/pdf').

    Returns:
        Extracted and potentially truncated text content.

    Raises:
        UnsupportedFileTypeError: If the content type is not supported.
        TextExtractionError: If extraction fails.
    """
    # Normalize content type (remove parameters like charset)
    base_content_type = content_type.split(";")[0].strip().lower()

    extractors = {
        "application/pdf": extract_text_from_pdf,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": extract_text_from_docx,
        "text/plain": extract_text_from_txt,
    }

    extractor = extractors.get(base_content_type)
    if extractor is None:
        raise UnsupportedFileTypeError(
            f"Unsupported file type: {content_type}. "
            f"Supported types: {', '.join(extractors.keys())}"
        )

    logger.info(
        "Extracting text from file",
        extra={
            "content_type": base_content_type,
            "file_size_bytes": len(file_bytes),
        },
    )

    text = extractor(file_bytes)
    will_truncate = len(text) > MAX_TEXT_LENGTH

    logger.info(
        "Text extraction complete",
        extra={
            "content_type": base_content_type,
            "extracted_chars": len(text),
            "will_truncate": will_truncate,
        },
    )

    return _truncate_text(text)
