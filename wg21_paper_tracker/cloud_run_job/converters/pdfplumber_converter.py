"""
PDFPlumber-based PDF to Markdown converter.
"""

from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.warning("PDFPlumber not available. Install with: pip install pdfplumber")


def convert_with_pdfplumber(pdf_path: Path) -> Optional[str]:
    """
    Convert PDF to Markdown using PDFPlumber.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Markdown content as string, or None if conversion fails.
    """
    if not PDFPLUMBER_AVAILABLE:
        logger.error("PDFPlumber is not available")
        return None

    try:
        logger.info(f"Attempting PDFPlumber conversion for: {pdf_path.name}")

        markdown_parts = []

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"Processing {total_pages} pages with PDFPlumber")

            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    # Extract text from page
                    text = page.extract_text()

                    if text:
                        markdown_parts.append(text)
                        markdown_parts.append("\n\n")

                    # Extract tables if any
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            if table:
                                markdown_parts.append("\n### Table\n\n")
                                # Convert table to markdown format
                                for row in table:
                                    if row:
                                        markdown_parts.append(
                                            "| "
                                            + " | ".join(
                                                str(cell) if cell else ""
                                                for cell in row
                                            )
                                            + " |\n"
                                        )
                                markdown_parts.append("\n")

                except Exception as e:
                    logger.warning(
                        f"Error processing page {page_num} of {pdf_path.name}: {str(e)}"
                    )
                    continue

        markdown_content = "".join(markdown_parts)

        if markdown_content and len(markdown_content.strip()) > 0:
            logger.info(f"PDFPlumber conversion successful for: {pdf_path.name}")
            logger.info(f"Extracted {len(markdown_content)} characters")
            return markdown_content
        else:
            logger.warning(
                f"PDFPlumber conversion returned empty content for: {pdf_path.name}"
            )
            return None

    except Exception as e:
        logger.error(
            f"PDFPlumber conversion failed for {pdf_path.name}: {str(e)}", exc_info=True
        )
        return None
