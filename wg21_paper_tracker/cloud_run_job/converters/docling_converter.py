"""
Docling-based PDF to Markdown converter.
"""

from pathlib import Path
from typing import Optional
import logging
logger = logging.getLogger(__name__)

try:
    from docling.document_converter import DocumentConverter  # type: ignore[import-untyped]
    from docling.datamodel.base_models import InputFormat  # type: ignore[import-untyped]

    DOCLING_AVAILABLE = True
except ImportError:
    DocumentConverter = None  # type: ignore[assignment,misc]
    InputFormat = None  # type: ignore[assignment,misc]
    DOCLING_AVAILABLE = False
    logger.warning("Docling not available. Install with: pip install docling")


def convert_with_docling(pdf_path: Path) -> Optional[str]:
    """
    Convert PDF to Markdown using Docling.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Markdown content as string, or None if conversion fails.
    """
    if not DOCLING_AVAILABLE or DocumentConverter is None:
        logger.error("Docling is not available")
        return None

    try:
        logger.info(f"Attempting Docling conversion for: {pdf_path.name}")

        # Initialize converter
        converter = DocumentConverter()

        # Convert PDF to document
        result = converter.convert(pdf_path)

        # Extract markdown
        markdown_content = result.document.export_to_markdown()

        if markdown_content and len(markdown_content.strip()) > 0:
            logger.info(f"Docling conversion successful for: {pdf_path.name}")
            logger.info(f"Extracted {len(markdown_content)} characters")
            return markdown_content
        else:
            logger.warning(
                f"Docling conversion returned empty content for: {pdf_path.name}"
            )
            return None

    except Exception as e:
        logger.error(
            f"Docling conversion failed for {pdf_path.name}: {str(e)}", exc_info=True
        )
        return None
