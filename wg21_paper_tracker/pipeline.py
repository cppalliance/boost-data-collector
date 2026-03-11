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
    # Requeue incomplete mailings so transient failures get retried (not just the latest)
    retry_dates = set(
        WG21Mailing.objects.filter(papers__isnull=True).values_list(
            "mailing_date", flat=True
        )
    )
    retry_dates.update(
        WG21Mailing.objects.filter(papers__is_downloaded=False).values_list(
            "mailing_date", flat=True
        )
    )
    if latest_mailing:
        retry_dates.add(latest_mailing.mailing_date)
    for current_m in all_mailings:
        if current_m["mailing_date"] in retry_dates and current_m[
            "mailing_date"
        ] not in [x["mailing_date"] for x in new_mailings]:
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
        # Normalize year once; use 0 when missing/empty/unparseable so you can fix later
        year_raw = m_info.get("year")
        if not year_raw or not str(year_raw).strip():
            year = 0
            logger.warning(
                "Mailing %s: year missing or empty, using 0 (fix later).",
                mailing_date,
            )
        else:
            try:
                year = int(str(year_raw).strip()[:4])
                if year <= 0:
                    year = 0
                    logger.warning(
                        "Mailing %s: year invalid, using 0 (fix later).",
                        mailing_date,
                    )
            except (ValueError, TypeError):
                year = 0
                logger.warning(
                    "Mailing %s: year not parseable %r, using 0 (fix later).",
                    mailing_date,
                    year_raw,
                )

        # Create/get mailing in DB
        mailing_obj, _ = get_or_create_mailing(mailing_date, title)

        # Fetch papers for this mailing
        papers = fetch_papers_for_mailing(str(year), mailing_date)
        if not papers:
            logger.info(
                "Mailing %s: no papers found (anchor/table may be missing).",
                mailing_date,
            )
            continue

        # Group papers by ID so we can choose the preferred source format per paper.
        papers_by_id = {}
        for p in papers:
            pid = (p["paper_id"] or "").strip().lower()
            if pid not in papers_by_id:
                papers_by_id[pid] = []
            papers_by_id[pid].append(p)

        def format_priority(ext: str) -> int:
            priorities = {"adoc": 1, "html": 2, "ps": 3, "pdf": 4}
            return priorities.get(ext.lower(), 100)

        raw_dir = get_raw_dir(mailing_date, year)

        skipped_downloaded = 0
        for pid, p_list in papers_by_id.items():
            # Skip only if this (paper_id, year) is already downloaded
            if WG21Paper.objects.filter(
                paper_id=pid,
                year=year,
                is_downloaded=True,
            ).exists():
                skipped_downloaded += 1
                continue

            # Pick the preferred format: adoc > html > ps > pdf.
            best_paper = min(p_list, key=lambda x: format_priority(x["type"]))

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
                    gcs_path = (
                        f"raw/wg21_paper_tracker/{year}/{mailing_date}/{filename}"
                    )
                    uploaded = _upload_to_gcs(bucket_name, local_path, gcs_path)
                else:
                    logger.warning(
                        "WG21_GCS_BUCKET is not configured; leaving %s as not downloaded.",
                        pid,
                    )

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
