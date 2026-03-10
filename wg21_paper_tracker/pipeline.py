"""
Pipeline for WG21 Paper Tracker.
Coordinates scraping, downloading, uploading to GCS, and updating the database.
"""

import time
import requests
import logging
from pathlib import Path

from django.conf import settings
from google.cloud import storage

from wg21_paper_tracker.fetcher import (
    fetch_all_mailings,
    fetch_papers_for_mailing,
)
from wg21_paper_tracker.models import WG21Mailing, WG21Paper
from wg21_paper_tracker.services import (
    get_or_create_mailing,
    get_or_create_paper,
)
from wg21_paper_tracker.workspace import get_raw_dir

logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT = 30
DOWNLOAD_MAX_RETRIES = 3
DOWNLOAD_RETRY_DELAY = 2


def _upload_to_gcs(
    bucket_name: str, source_path: Path, destination_blob_name: str
) -> bool:
    """Uploads a file to the bucket."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)

        blob.upload_from_filename(str(source_path))
        logger.info(
            "Uploaded %s to gs://%s/%s",
            source_path.name,
            bucket_name,
            destination_blob_name,
        )
        return True
    except Exception as e:
        logger.error("Failed to upload to GCS: %s", e)
        return False


def _download_file(url: str, filepath: Path) -> bool:
    """Download file from URL to filepath with retries and 30s timeout."""
    for attempt in range(1, DOWNLOAD_MAX_RETRIES + 1):
        try:
            logger.info(
                "Downloading %s to %s (attempt %d/%d)",
                url,
                filepath,
                attempt,
                DOWNLOAD_MAX_RETRIES,
            )
            response = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)
            response.raise_for_status()

            # For text-based files, save as UTF-8. For binary (like PDF), save as bytes.
            content_type = response.headers.get("content-type", "")
            if "text" in content_type:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(
                        response.content.decode(
                            response.apparent_encoding or "utf-8",
                            errors="replace",
                        )
                    )
            else:
                with open(filepath, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True
        except Exception as e:
            if attempt < DOWNLOAD_MAX_RETRIES:
                logger.warning(
                    "Download attempt %d/%d failed for %s: %s. Retrying in %ds.",
                    attempt,
                    DOWNLOAD_MAX_RETRIES,
                    url,
                    e,
                    DOWNLOAD_RETRY_DELAY,
                )
                time.sleep(DOWNLOAD_RETRY_DELAY)
            else:
                logger.error(
                    "Failed to download %s after %d attempts: %s",
                    url,
                    DOWNLOAD_MAX_RETRIES,
                    e,
                )
    return False


def run_tracker_pipeline() -> int:
    """
    Run the WG21 tracker pipeline.
    Returns the number of new papers downloaded and uploaded.
    """
    bucket_name = settings.WG21_GCS_BUCKET
    if not bucket_name:
        logger.warning("WG21_GCS_BUCKET not set. Will download but not upload to GCS.")

    # 1. Get latest mailing from DB
    latest_mailing = (
        WG21Mailing.objects.exclude(mailing_date="unknown")
        .order_by("-mailing_date")
        .first()
    )
    latest_date = latest_mailing.mailing_date if latest_mailing else "1970-01"

    # 2. Fetch all mailings
    all_mailings = fetch_all_mailings()
    if not all_mailings:
        logger.warning("No mailings found on WG21 site.")
        return 0

    # Filter newer mailings
    new_mailings = [m for m in all_mailings if m["mailing_date"] > latest_date]
    # Also check the latest one again just in case new papers were added
    if latest_mailing and latest_mailing.mailing_date not in [
        m["mailing_date"] for m in new_mailings
    ]:
        # We re-check the most recent mailing from the DB to catch late additions
        # Find the matching dict from all_mailings
        current_m = next(
            (
                m
                for m in all_mailings
                if m["mailing_date"] == latest_mailing.mailing_date
            ),
            None,
        )
        if current_m:
            new_mailings.append(current_m)

    # Sort chronologically (oldest to newest)
    new_mailings.sort(key=lambda x: x["mailing_date"])

    logger.info(
        "Pipeline: latest_date=%s, all_mailings=%d, mailings_to_process=%s",
        latest_date,
        len(all_mailings),
        [m["mailing_date"] for m in new_mailings],
    )
    total_new_papers = 0

    for m_info in new_mailings:
        mailing_date = m_info["mailing_date"]
        title = m_info["title"]
        year = int(m_info["year"]) if m_info["year"] else None

        # Create/get mailing in DB
        mailing_obj, _ = get_or_create_mailing(mailing_date, title)

        # Fetch papers for this mailing
        papers = fetch_papers_for_mailing(year, mailing_date)
        if not papers:
            logger.info(
                "Mailing %s: no papers found (anchor/table may be missing).",
                mailing_date,
            )
            continue

        # Group papers by ID to prioritize PDF over HTML (paper_id is case-insensitive)
        papers_by_id = {}
        for p in papers:
            pid = (p["paper_id"] or "").strip().lower()
            if pid not in papers_by_id:
                papers_by_id[pid] = []
            papers_by_id[pid].append(p)

        def format_priority(ext: str) -> int:
            priorities = {"pdf": 1, "html": 2, "adoc": 3, "ps": 4}
            return priorities.get(ext.lower(), 100)

        raw_dir = get_raw_dir(mailing_date)

        skipped_downloaded = 0
        year_val = year if year is not None else 0
        for pid, p_list in papers_by_id.items():
            # Skip only if this (paper_id, year) is already downloaded
            if WG21Paper.objects.filter(
                paper_id=pid,
                year=year_val,
                is_downloaded=True,
            ).exists():
                skipped_downloaded += 1
                continue

            # Pick the best format
            p_list.sort(key=lambda x: format_priority(x["type"]))
            best_paper = p_list[0]

            raw_filename = (best_paper.get("filename") or "").strip()
            filename = Path(raw_filename).name
            if not filename or filename != raw_filename:
                logger.warning(
                    "Skipping paper %s due to unsafe filename %r",
                    pid,
                    raw_filename,
                )
                continue
            local_path = raw_dir / filename
            url = best_paper["url"]

            # Download
            if _download_file(url, local_path):
                uploaded = False
                if bucket_name:
                    gcs_path = f"raw/wg21_papers/{mailing_date}/{filename}"
                    uploaded = _upload_to_gcs(bucket_name, local_path, gcs_path)
                else:
                    # If no GCS, simulate success so DB is updated
                    uploaded = True

                # Persist DB
                doc_date_str = best_paper["document_date"]
                # Parse date if available
                from django.utils.dateparse import parse_date

                doc_date = None
                if doc_date_str:
                    try:
                        doc_date = parse_date(doc_date_str)
                    except Exception as e:
                        logger.warning(
                            "Failed to parse document date: %s: %s",
                            doc_date_str,
                            e,
                        )
                        doc_date = None

                paper_obj, _created = get_or_create_paper(
                    paper_id=pid,
                    url=url,
                    title=best_paper["title"],
                    document_date=doc_date,
                    mailing=mailing_obj,
                    subgroup=best_paper["subgroup"],
                    author_names=best_paper["authors"],
                    year=year,
                )

                if uploaded:
                    paper_obj.is_downloaded = True
                    paper_obj.save(update_fields=["is_downloaded"])
                    total_new_papers += 1

                # Clean up local file to save space
                # try:
                #     # local_path.unlink()
                # except Exception as e:
                #     logger.warning(
                #         "Could not delete temp file %s: %s", local_path, e
                #     )

        if skipped_downloaded:
            logger.info(
                "Mailing %s: skipped %d papers (already downloaded).",
                mailing_date,
                skipped_downloaded,
            )

    return total_new_papers
