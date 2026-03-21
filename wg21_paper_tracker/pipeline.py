"""
Pipeline for WG21 Paper Tracker.
Coordinates scraping and updating the database (metadata only; no file download or GCS).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from django.utils.dateparse import parse_date

from wg21_paper_tracker.fetcher import (
    fetch_all_mailings,
    fetch_papers_for_mailing,
)
from wg21_paper_tracker.models import WG21Mailing
from wg21_paper_tracker.services import (
    get_or_create_mailing,
    get_or_create_paper,
)

logger = logging.getLogger(__name__)

# WG21 mailing_date and typical CSV column (e.g. 2025-03, 2026-01)
_MAILING_DATE_LABEL_RE = re.compile(r"^\d{4}-\d{2}$")


def _normalize_mailing_date_label(label: str, *, field_name: str) -> str:
    s = label.strip()
    if not _MAILING_DATE_LABEL_RE.match(s):
        raise ValueError(
            f"Invalid {field_name} {label!r}; "
            "expected YYYY-MM (e.g. 2025-03), same as WG21 / CSV mailing keys."
        )
    return s


def _mailing_date_in_run_scope(
    mailing_date: str,
    *,
    latest_date: str,
    from_mailing_date: Optional[str],
    to_mailing_date: Optional[str],
) -> bool:
    """Whether a mailing key is selected for this run (before retry merge)."""
    if from_mailing_date is None and to_mailing_date is None:
        return mailing_date > latest_date

    if from_mailing_date is not None and mailing_date < from_mailing_date:
        return False
    if to_mailing_date is not None and mailing_date > to_mailing_date:
        return False
    if from_mailing_date is None and to_mailing_date is not None:
        return mailing_date > latest_date
    return True


def _format_priority(ext: str) -> int:
    """Prefer adoc > html > ps > pdf when multiple formats exist for one paper_id."""
    priorities = {"adoc": 1, "html": 2, "ps": 3, "pdf": 4}
    return priorities.get(ext.lower(), 100)


def _parse_mailing_year(m_info: dict) -> int:
    """Return 4-digit year from the index mailing dict, or 0 if missing/invalid."""
    mailing_date = m_info["mailing_date"]
    year_raw = m_info.get("year")
    if not year_raw or not str(year_raw).strip():
        logger.warning(
            "Mailing %s: year missing or empty, using 0 (fix later).",
            mailing_date,
        )
        return 0
    try:
        year = int(str(year_raw).strip()[:4])
    except (ValueError, TypeError):
        logger.warning(
            "Mailing %s: year not parseable %r, using 0 (fix later).",
            mailing_date,
            year_raw,
        )
        return 0
    if year <= 0 or year > datetime.now().year + 1:
        logger.warning(
            "Mailing %s: year invalid, using 0 (fix later).",
            mailing_date,
        )
        return 0
    return year


def _group_fetched_papers_by_id(
    papers: list[dict[str, Any]], mailing_date: str
) -> dict[str, list[dict[str, Any]]]:
    """Bucket fetcher rows by normalized paper_id."""
    papers_by_id: dict[str, list[dict[str, Any]]] = {}
    for p in papers:
        pid = (p.get("paper_id") or "").strip().lower()
        if not pid:
            logger.warning(
                "Skipping paper entry without a paper_id in mailing %s: %r",
                mailing_date,
                p,
            )
            continue
        papers_by_id.setdefault(pid, []).append(p)
    return papers_by_id


def _valid_paper_entries_for_id(
    p_list: list[dict[str, Any]], pid: str, mailing_date: str
) -> list[dict[str, Any]]:
    """Keep rows that have type, url, and title (all non-empty)."""
    valid: list[dict[str, Any]] = []
    for p in p_list:
        type_val = (
            (p.get("type") or "").strip() if isinstance(p.get("type"), str) else ""
        )
        url_val = (p.get("url") or "").strip() if isinstance(p.get("url"), str) else ""
        title_val = (
            (p.get("title") or "").strip() if isinstance(p.get("title"), str) else ""
        )
        if not type_val or not url_val or not title_val:
            logger.debug(
                "Skipping malformed paper entry for %s in mailing %s: %r",
                pid,
                mailing_date,
                p,
            )
            continue
        valid.append(p)
    return valid


def _choose_best_format_entry(valid_list: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick one row by format priority (adoc first). Precondition: valid_list non-empty."""
    return min(
        valid_list,
        key=lambda x: _format_priority(str(x.get("type") or "").strip()),
    )


def _parse_scraped_document_date(doc_date_str: Any) -> Optional[date]:
    if not doc_date_str:
        return None
    try:
        return parse_date(str(doc_date_str).strip())
    except Exception as e:
        logger.warning(
            "Failed to parse document date: %s: %s",
            doc_date_str,
            e,
        )
        return None


def _upsert_paper_from_scraped_row(
    pid: str,
    best_paper: dict[str, Any],
    mailing_obj: WG21Mailing,
    year: int,
    mailing_date: str,
) -> Optional[str]:
    """
    Create or update WG21Paper from the chosen fetcher row.
    Returns the document URL if a **new** row was inserted, else None.
    """
    url = (best_paper.get("url") or "").strip()
    paper_title = (best_paper.get("title") or "").strip()
    subgroup = (best_paper.get("subgroup") or "").strip()
    authors = best_paper.get("authors")
    if not isinstance(authors, list):
        authors = []
    if not url or not paper_title:
        logger.warning(
            "Skipping paper %s in mailing %s due to missing required fields: %r",
            pid,
            mailing_date,
            best_paper,
        )
        return None

    doc_date = _parse_scraped_document_date(best_paper.get("document_date"))
    _paper_obj, created = get_or_create_paper(
        paper_id=pid,
        url=url,
        title=paper_title,
        document_date=doc_date,
        mailing=mailing_obj,
        subgroup=subgroup,
        author_names=authors,
        year=year,
    )
    return url if created else None


def _process_single_mailing(m_info: dict) -> list[str]:
    """
    For one mailing from the index: normalize year, get/create WG21Mailing,
    fetch paper rows from the site, upsert WG21Paper rows.

    Returns URLs for papers **newly created** in this run for this mailing.
    """
    mailing_date = m_info["mailing_date"]
    title = m_info["title"]
    year = _parse_mailing_year(m_info)
    mailing_obj, _ = get_or_create_mailing(mailing_date, title)

    papers = fetch_papers_for_mailing(str(year), mailing_date)
    if not papers:
        logger.info(
            "Mailing %s: no papers found (anchor/table may be missing).",
            mailing_date,
        )
        return []

    papers_by_id = _group_fetched_papers_by_id(papers, mailing_date)
    new_urls: list[str] = []

    for pid, p_list in papers_by_id.items():
        valid_list = _valid_paper_entries_for_id(p_list, pid, mailing_date)
        if not valid_list:
            logger.warning(
                "Skipping paper %s in mailing %s: no valid entries (type, url, title)",
                pid,
                mailing_date,
            )
            continue
        best_paper = _choose_best_format_entry(valid_list)
        url = _upsert_paper_from_scraped_row(
            pid, best_paper, mailing_obj, year, mailing_date
        )
        if url:
            new_urls.append(url)

    return new_urls


@dataclass(frozen=True)
class TrackerPipelineResult:
    """Result of run_tracker_pipeline: URLs for papers newly created in this run."""

    new_paper_urls: tuple[str, ...] = field(default_factory=tuple)

    @property
    def new_paper_count(self) -> int:
        return len(self.new_paper_urls)


def run_tracker_pipeline(
    *,
    from_mailing_date: Optional[str] = None,
    to_mailing_date: Optional[str] = None,
) -> TrackerPipelineResult:
    """
    Run the WG21 tracker pipeline: scrape mailings, upsert papers in the DB.
    Returns URLs for rows created in this run (for GitHub repository_dispatch).

    Mailing keys are ``YYYY-MM`` (WG21 / CSV style). Selection:

    - Neither ``from_mailing_date`` nor ``to_mailing_date``: process mailings with
      ``mailing_date`` strictly newer than the latest ``WG21Mailing`` in the DB.
    - ``from_mailing_date`` only: ``mailing_date >= from_mailing_date``.
    - ``to_mailing_date`` only: ``mailing_date > latest_in_db`` and
      ``mailing_date <= to_mailing_date`` (incremental runs capped at ``to``).
    - Both: ``from_mailing_date <= mailing_date <= to_mailing_date`` (inclusive).

    ``from_mailing_date`` must not be lexicographically after ``to_mailing_date``.
    """
    if from_mailing_date is not None:
        from_mailing_date = _normalize_mailing_date_label(
            from_mailing_date, field_name="from_mailing_date"
        )
    if to_mailing_date is not None:
        to_mailing_date = _normalize_mailing_date_label(
            to_mailing_date, field_name="to_mailing_date"
        )
    if (
        from_mailing_date is not None
        and to_mailing_date is not None
        and from_mailing_date > to_mailing_date
    ):
        raise ValueError(
            f"from_mailing_date {from_mailing_date!r} is after "
            f"to_mailing_date {to_mailing_date!r}."
        )

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
        return TrackerPipelineResult()

    # Filter mailings to process
    new_mailings = [
        m
        for m in all_mailings
        if _mailing_date_in_run_scope(
            m["mailing_date"],
            latest_date=latest_date,
            from_mailing_date=from_mailing_date,
            to_mailing_date=to_mailing_date,
        )
    ]
    if from_mailing_date is None and to_mailing_date is None:
        baseline_desc = f"latest_in_db={latest_date}"
    else:
        parts: list[str] = []
        if from_mailing_date is not None:
            parts.append(f"from={from_mailing_date}")
        if to_mailing_date is not None:
            parts.append(f"to={to_mailing_date}")
        if from_mailing_date is None:
            parts.append(f"latest_in_db={latest_date}")
        baseline_desc = ", ".join(parts)

    # Requeue incomplete mailings so transient failures get retried (not just the latest)
    retry_dates = set(
        WG21Mailing.objects.filter(papers__isnull=True).values_list(
            "mailing_date", flat=True
        )
    )
    if latest_mailing:
        retry_dates.add(latest_mailing.mailing_date)
    retry_dates = {
        d
        for d in retry_dates
        if _mailing_date_in_run_scope(
            d,
            latest_date=latest_date,
            from_mailing_date=from_mailing_date,
            to_mailing_date=to_mailing_date,
        )
    }
    for current_m in all_mailings:
        if current_m["mailing_date"] in retry_dates and current_m[
            "mailing_date"
        ] not in [x["mailing_date"] for x in new_mailings]:
            new_mailings.append(current_m)

    # Sort chronologically (oldest to newest)
    new_mailings.sort(key=lambda x: x["mailing_date"])

    logger.info(
        "Pipeline: %s, all_mailings=%d, mailings_to_process=%s",
        baseline_desc,
        len(all_mailings),
        [m["mailing_date"] for m in new_mailings],
    )
    new_urls: list[str] = []
    for m_info in new_mailings:
        new_urls.extend(_process_single_mailing(m_info))

    return TrackerPipelineResult(new_paper_urls=tuple(new_urls))
