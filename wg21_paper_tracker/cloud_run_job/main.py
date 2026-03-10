import os
import logging
from pathlib import Path
import tempfile
from typing import Optional

from google.cloud import storage

from converters.docling_converter import convert_with_docling
from converters.pdfplumber_converter import convert_with_pdfplumber
from converters.openai_converter import convert_with_openai

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MIN_CONTENT_LENGTH = 50


def is_content_valid(content: Optional[str]) -> bool:
    if not content:
        return False
    content_stripped = content.strip()
    if len(content_stripped) < MIN_CONTENT_LENGTH:
        return False
    error_patterns = [
        "traceback",
        "exception:",
        "error:",
        "failed to",
        "unable to convert",
        "conversion failed",
        "error processing",
    ]
    content_lower = content_stripped.lower()
    first_part = content_lower[:1000]
    for pattern in error_patterns:
        if pattern in first_part:
            if pattern in ("error:", "exception:"):
                return False
            idx = first_part.find(pattern)
            if idx < 100:
                return False
    return True


def convert_pdf_to_md(pdf_path: Path) -> str:
    logger.info("Attempting Docling conversion...")
    content = convert_with_docling(pdf_path)
    if is_content_valid(content):
        return content

    logger.info("Attempting PDFPlumber conversion...")
    content = convert_with_pdfplumber(pdf_path)
    if is_content_valid(content):
        return content

    logger.info("Attempting OpenAI conversion...")
    content = convert_with_openai(pdf_path)
    if is_content_valid(content):
        return content

    return ""


def main():
    bucket_name = os.getenv("WG21_GCS_BUCKET")
    if not bucket_name:
        logger.error("WG21_GCS_BUCKET env var not set.")
        return

    client = storage.Client()
    bucket = client.bucket(bucket_name)

    raw_prefix = "raw/wg21_paper_tracker/"
    converted_prefix = "converted/wg21_papers/"

    blobs = client.list_blobs(bucket, prefix=raw_prefix)

    with tempfile.TemporaryDirectory() as tmpdir:
        for blob in blobs:
            if not blob.name.lower().endswith(".pdf"):
                continue

            local_pdf_path = Path(tmpdir) / "temp.pdf"
            try:
                # e.g. raw/wg21_papers/2025-02/p0149r1.pdf -> 2025-02/p0149r1.pdf
                relative_path = blob.name[len(raw_prefix) :]
                md_relative_path = relative_path.rsplit(".", 1)[0] + ".md"
                md_blob_name = f"{converted_prefix}{md_relative_path}"

                md_blob = bucket.blob(md_blob_name)
                if md_blob.exists():
                    logger.info("Skipping %s, MD already exists.", blob.name)
                    continue

                logger.info("Downloading %s to process...", blob.name)
                blob.download_to_filename(str(local_pdf_path))

                logger.info("Converting %s...", blob.name)
                md_content = convert_pdf_to_md(local_pdf_path)

                if md_content:
                    md_blob.upload_from_string(md_content, content_type="text/markdown")
                    logger.info("Successfully converted and uploaded %s", md_blob_name)
                else:
                    logger.error("Failed to convert %s", blob.name)
            except Exception:
                logger.exception("Failed processing %s", blob.name)
            finally:
                if local_pdf_path.exists():
                    local_pdf_path.unlink()


if __name__ == "__main__":
    main()
