"""
OpenAI/OpenRouter-based PDF to Markdown converter with OCR.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Base configuration fallback


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")

try:
    from pdf2image import convert_from_path
    from PIL import Image, ImageOps

    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logger.warning(
        "pdf2image/PIL not available. Install with: pip install pdf2image pillow"
    )


def pdf_to_images(pdf_path: Path) -> tuple[Optional[Path], list[Path]]:
    """
    Convert PDF pages to image files on disk (one per page) to avoid loading all into memory.

    Writes images into a temporary directory and returns (tmp_dir, paths). Caller must process
    each path and then remove tmp_dir (e.g. shutil.rmtree) so only the current page is resident.

    Note: pdf2image should automatically handle PDF rotation metadata; we also apply
    additional rotation correction in correct_image_rotation() when loading each image.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        (tmp_dir, list of image paths). tmp_dir is None on failure or if pdf2image unavailable;
        paths are in page order. Caller must cleanup tmp_dir when not None.
    """
    if not PDF2IMAGE_AVAILABLE:
        logger.error("pdf2image is not available")
        return (None, [])

    try:
        logger.info(f"Converting PDF to images: {pdf_path.name}")
        tmp_dir = Path(tempfile.mkdtemp(prefix="wg21_pdf_"))
        try:
            path_strs = convert_from_path(
                pdf_path,
                dpi=200,
                paths_only=True,
                output_folder=str(tmp_dir),
            )
            paths = [Path(p) for p in path_strs]
            logger.info(f"Converted {len(paths)} pages to images")
            return (tmp_dir, paths)
        except Exception:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise
    except Exception as e:
        logger.error(f"Failed to convert PDF to images: {str(e)}", exc_info=True)
        return (None, [])


def correct_image_rotation(image: Image.Image) -> Image.Image:
    """
    Correct image rotation using EXIF data and heuristics.

    Args:
        image: PIL Image object.

    Returns:
        Corrected PIL Image object.
    """
    try:
        # First, try to correct using EXIF orientation data
        # This handles images that have rotation metadata
        corrected_image = ImageOps.exif_transpose(image)

        # If the image was rotated, log it
        if corrected_image != image:
            logger.debug("Image rotation corrected using EXIF data")
            return corrected_image

        # If no EXIF data, check if image might be rotated
        # For PDF pages, we can check if width > height suggests landscape
        # But we'll keep the original orientation as PDFs can be in any orientation
        # The OpenAI vision model can handle rotated text, but it's better to correct it

        return corrected_image

    except Exception as e:
        logger.warning(f"Error correcting image rotation: {str(e)}")
        return image


def image_to_base64(image: Image.Image) -> str:
    """
    Convert PIL Image to base64 string.
    Automatically corrects rotation before encoding.

    Args:
        image: PIL Image object.

    Returns:
        Base64 encoded string.
    """
    # Correct rotation before encoding
    corrected_image = correct_image_rotation(image)

    buffered = io.BytesIO()
    corrected_image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str


def convert_page_with_openai(
    image_base64: str, page_num: int, total_pages: int
) -> Optional[str]:
    """
    Convert a single page image to markdown using OpenAI/OpenRouter.

    Args:
        image_base64: Base64 encoded image string.
        page_num: Current page number.
        total_pages: Total number of pages.

    Returns:
        Markdown content for the page, or None if conversion fails.
    """
    if not OPENROUTER_API_KEY:
        logger.error("OpenRouter API key is not set")
        return None

    url = f"{OPENROUTER_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a document conversion assistant. Convert the provided PDF page image to clean, well-formatted Markdown. Preserve the structure, formatting, tables, and content as accurately as possible. Use proper markdown syntax for headers, lists, tables, and code blocks. If the image appears rotated, read the text in its current orientation and convert it correctly.",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Convert this PDF page ({page_num} of {total_pages}) to Markdown format. Preserve all text, structure, and formatting. If the page appears rotated, read and convert the text in its correct orientation.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                    },
                ],
            },
        ],
        "max_tokens": 4000,
    }

    max_attempts = 3  # initial + 2 retries
    retry_delays = [1, 2]  # exponential backoff in seconds

    for attempt in range(max_attempts):
        try:
            logger.info(
                f"Converting page {page_num}/{total_pages} with OpenAI/OpenRouter"
                + (f" (attempt {attempt + 1}/{max_attempts})" if attempt > 0 else "")
            )

            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()

            result = response.json()
            markdown_content = result["choices"][0]["message"]["content"]

            logger.info(
                f"Successfully converted page {page_num} with OpenAI/OpenRouter"
            )
            return markdown_content

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
        ) as e:
            retryable = attempt < max_attempts - 1
            if retryable:
                delay = retry_delays[attempt]
                logger.warning(
                    f"Transient error on page {page_num} ({type(e).__name__}), "
                    f"retrying in {delay}s (attempt {attempt + 1}/{max_attempts})"
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"OpenAI/OpenRouter conversion failed for page {page_num}: {str(e)}",
                    exc_info=True,
                )
                return None

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else None
            retryable = (
                attempt < max_attempts - 1
                and status_code is not None
                and (status_code == 429 or 500 <= status_code < 600)
            )
            if retryable:
                delay = retry_delays[attempt]
                logger.warning(
                    f"HTTP {status_code} on page {page_num}, "
                    f"retrying in {delay}s (attempt {attempt + 1}/{max_attempts})"
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"OpenAI/OpenRouter conversion failed for page {page_num}: {str(e)}",
                    exc_info=True,
                )
                return None

        except Exception as e:
            logger.error(
                f"OpenAI/OpenRouter conversion failed for page {page_num}: {str(e)}",
                exc_info=True,
            )
            return None

    return None


def convert_with_openai(pdf_path: Path) -> Optional[str]:
    """
    Convert PDF to Markdown using OpenAI/OpenRouter with OCR.
    Processes each page as an image.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Markdown content as string, or None if conversion fails.
    """
    if not OPENROUTER_API_KEY:
        logger.error("OpenRouter API key is not set in environment variables")
        return None

    if not PDF2IMAGE_AVAILABLE:
        logger.error("pdf2image is required for OpenAI conversion")
        return None

    try:
        logger.info(f"Attempting OpenAI/OpenRouter conversion for: {pdf_path.name}")

        try:
            # Convert PDF to image files on disk (avoids loading all pages into memory)
            tmp_dir, paths = pdf_to_images(pdf_path)
            if not paths:
                logger.error(f"Failed to convert PDF to images: {pdf_path.name}")
                return None

            total_pages = len(paths)
            markdown_parts = []
            successful_pages = 0
            # Process each page: load one image at a time, convert, then move on
            for page_num, image_path in enumerate(paths, 1):
                try:
                    with Image.open(image_path) as img:
                        img.load()
                        image_base64 = image_to_base64(img)
                    # Convert page with OpenAI
                    page_markdown = convert_page_with_openai(
                        image_base64, page_num, total_pages
                    )

                    if page_markdown:
                        markdown_parts.append(page_markdown)
                        markdown_parts.append("\n\n")
                        successful_pages += 1
                    else:
                        logger.warning(f"Failed to convert page {page_num} with OpenAI")
                        markdown_parts.append(
                            f"## Page {page_num}\n\n*[Page content unavailable]*\n\n"
                        )

                except Exception as e:
                    logger.error(
                        f"Error processing page {page_num}: {str(e)}",
                        exc_info=True,
                    )
                    markdown_parts.append(
                        f"## Page {page_num}\n\n*[Page content unavailable]*\n\n"
                    )
                    continue
        finally:
            if tmp_dir is not None:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        markdown_content = "".join(markdown_parts)

        if successful_pages > 0 and markdown_content.strip():
            logger.info(f"OpenAI/OpenRouter conversion successful for: {pdf_path.name}")
            logger.info(
                f"Extracted {len(markdown_content)} characters from {total_pages} pages"
            )
            return markdown_content
        logger.warning(
            "OpenAI/OpenRouter conversion produced no usable pages for: %s",
            pdf_path.name,
        )
        return None

    except Exception as e:
        logger.error(
            f"OpenAI/OpenRouter conversion failed for {pdf_path.name}: {str(e)}",
            exc_info=True,
        )
        return None
