"""Utilities - Helper functions and common utilities.

This module contains utility functions that are used across the application.
"""

from app.utils.text_extraction import (
    TextExtractionError,
    UnsupportedFileTypeError,
    extract_text,
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_txt,
)

__all__ = [
    # Text extraction functions
    "extract_text",
    "extract_text_from_pdf",
    "extract_text_from_docx",
    "extract_text_from_txt",
    # Text extraction exceptions
    "TextExtractionError",
    "UnsupportedFileTypeError",
]
