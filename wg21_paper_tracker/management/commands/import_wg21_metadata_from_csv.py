"""
Management command: import_wg21_metadata_from_csv

Reads workspace/wg21_paper_tracker/metadata.csv (or a given path) and fills
WG21Mailing, WG21Paper, and WG21PaperAuthor using get_or_create_mailing and
get_or_create_paper. Handles missing mailing_date via a placeholder mailing
(unknown / Unknown).
"""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError
from django.utils.dateparse import parse_date

from wg21_paper_tracker.models import WG21Paper
from wg21_paper_tracker.services import (
    get_or_create_mailing,
    get_or_create_paper,
    get_or_create_paper_author,
)
from wg21_paper_tracker.workspace import get_workspace_root

logger = logging.getLogger(__name__)

MAILING_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}$")
TITLE_MAX_LENGTH = 1024
PLACEHOLDER_MAILING_DATE = "unknown"
PLACEHOLDER_MAILING_TITLE = "Unknown"


def _norm(s: str) -> str:
    """Return the string stripped of leading/trailing whitespace, or empty string if None."""
    return (s or "").strip()


def _normalize_title(raw: str) -> str:
    """Replace internal newlines with space and truncate to model max_length."""
    if not raw:
        return ""
    one_line = " ".join(raw.split())
    return one_line[:TITLE_MAX_LENGTH] if len(one_line) > TITLE_MAX_LENGTH else one_line


def _resolve_mailing_date(csv_mailing_date: str) -> tuple[str, str]:
    """
    Return (mailing_date, title) for this row.
    If CSV mailing_date is non-empty and YYYY-MM, use it with synthetic title.
    Otherwise use placeholder mailing_date="unknown", title="Unknown".
    """
    cleaned = _norm(csv_mailing_date)
    if cleaned and MAILING_DATE_PATTERN.match(cleaned):
        return cleaned, f"{cleaned} (from metadata)"
    return PLACEHOLDER_MAILING_DATE, PLACEHOLDER_MAILING_TITLE


def _parse_document_date(date_str: str):
    """Return date or None from CSV date column (e.g. YYYY-MM-DD). Invalid values return None."""
    cleaned = _norm(date_str)
    if not cleaned:
        return None
    # try:
    return parse_date(cleaned)
    # except (ValueError, TypeError):
    #     return None


def _author_names_from_csv(author_str: str) -> list[str]:
    """Split author column by comma, strip each, drop empty."""
    cleaned = _norm(author_str)
    if not cleaned:
        return []
    return [a.strip() for a in cleaned.split(",") if a.strip()]


def _read_csv_rows(csv_path: Path):
    """Yield dicts for each row with normalized keys and values."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out = {}
            for k, v in row.items():
                if k is None:
                    continue
                key = k.strip().lower()
                out[key] = _norm(v) if v is not None else ""
            # Normalize title (multi-line -> single line, truncate)
            if "title" in out:
                out["title"] = _normalize_title(out["title"])
            yield out


@dataclass(frozen=True)
class _CsvImportRow:
    paper_id: str
    url: str
    mailing_date: str
    mailing_title: str
    document_date: Optional[date]
    year: Optional[int]
    title: str
    subgroup: str
    author_names: list[str]


def _parse_csv_import_row(row: dict) -> _CsvImportRow | None:
    """Return parsed row, or None when paper_id or url is missing."""
    paper_id = (row.get("paper_id", "") or "").strip().lower()
    url = row.get("url", "")
    if not paper_id or not url:
        return None

    mailing_date, mailing_title = _resolve_mailing_date(row.get("mailing_date", ""))
    document_date = _parse_document_date(row.get("date", ""))
    if mailing_date and MAILING_DATE_PATTERN.match(mailing_date):
        year = int(mailing_date[:4])
    elif document_date is not None:
        year = document_date.year
    else:
        year = None
    title = row.get("title", "") or paper_id
    subgroup = row.get("subgroup", "")
    author_names = _author_names_from_csv(row.get("author", ""))
    return _CsvImportRow(
        paper_id=paper_id,
        url=url,
        mailing_date=mailing_date,
        mailing_title=mailing_title,
        document_date=document_date,
        year=year,
        title=title,
        subgroup=subgroup,
        author_names=author_names,
    )


def _log_dry_run_row(parsed: _CsvImportRow) -> None:
    logger.info(
        "Would create/update paper %s -> mailing %r, document_date=%s, authors=%d",
        parsed.paper_id,
        parsed.mailing_date,
        parsed.document_date,
        len(parsed.author_names),
    )


def _attach_csv_authors_to_paper(paper: WG21Paper, author_names: list[str]) -> None:
    from cppa_user_tracker.services import (
        get_or_create_wg21_paper_author_profile,
    )

    for i, name in enumerate(author_names):
        profile, _ = get_or_create_wg21_paper_author_profile(name)
        get_or_create_paper_author(paper, profile, i + 1)


def _update_paper_on_integrity_error(
    parsed: _CsvImportRow, exc: IntegrityError, stats: dict
) -> None:
    mailing, _ = get_or_create_mailing(parsed.mailing_date, parsed.mailing_title)
    try:
        lookup_year = parsed.year if parsed.year is not None else 0
        paper = WG21Paper.objects.filter(
            paper_id=parsed.paper_id, year=lookup_year
        ).first()
        if paper is None:
            stats["skipped"] += 1
            logger.error("Error for paper_id=%s: %s", parsed.paper_id, exc)
            return
        paper.url = parsed.url
        paper.title = parsed.title
        paper.document_date = parsed.document_date
        paper.mailing = mailing
        paper.subgroup = parsed.subgroup
        if parsed.year is not None:
            paper.year = parsed.year
        paper.save()
        stats["papers_updated"] += 1
        if parsed.author_names:
            _attach_csv_authors_to_paper(paper, parsed.author_names)
    except Exception:
        stats["skipped"] += 1
        logger.exception(
            "Error for paper_id=%s (after IntegrityError).",
            parsed.paper_id,
        )


def _upsert_paper_from_csv_row(parsed: _CsvImportRow, stats: dict) -> None:
    try:
        mailing, mailing_created = get_or_create_mailing(
            parsed.mailing_date, parsed.mailing_title
        )
        if mailing_created:
            stats["mailings_created"] += 1

        _paper, paper_created = get_or_create_paper(
            paper_id=parsed.paper_id,
            url=parsed.url,
            title=parsed.title,
            document_date=parsed.document_date,
            mailing=mailing,
            subgroup=parsed.subgroup,
            author_names=parsed.author_names if parsed.author_names else None,
            year=parsed.year,
        )
        if paper_created:
            stats["papers_created"] += 1
        else:
            stats["papers_updated"] += 1
    except IntegrityError as e:
        _update_paper_on_integrity_error(parsed, e, stats)
    except Exception as e:
        stats["skipped"] += 1
        logger.error("Error for paper_id=%s: %s", parsed.paper_id, e)


class Command(BaseCommand):
    help = (
        "Read metadata CSV and fill WG21Mailing and WG21Paper (and authors). "
        "CSV columns: filename, paper_id, url, title, author, date, mailing_date, subgroup. "
        "When mailing_date is empty, papers are linked to a single 'unknown' mailing."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-file",
            type=Path,
            default=None,
            help="Path to metadata CSV (default: workspace/wg21_paper_tracker/metadata.csv)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only read CSV and report what would be done; do not write to DB.",
        )

    def handle(self, *args, **options):
        csv_path = options.get("csv_file") or (get_workspace_root() / "metadata.csv")
        dry_run = options["dry_run"]

        if not csv_path.exists():
            raise CommandError(f"File not found: {csv_path}")

        if dry_run:
            logger.info("Dry run: no DB writes.")

        stats = {
            "rows": 0,
            "skipped": 0,
            "mailings_created": 0,
            "papers_created": 0,
            "papers_updated": 0,
        }

        for row in _read_csv_rows(csv_path):
            stats["rows"] += 1
            try:
                parsed = _parse_csv_import_row(row)
            except Exception as e:
                stats["skipped"] += 1
                paper_id = (row.get("paper_id", "") or "").strip().lower()
                logger.error(
                    "Error parsing document date for paper_id=%s: %s",
                    paper_id,
                    e,
                )
                continue

            if parsed is None:
                stats["skipped"] += 1
                if stats["skipped"] <= 5:
                    logger.debug(
                        "Skipping row: missing paper_id or url: %s",
                        row.get("paper_id", "") or row.get("url", "")[:50],
                    )
                continue

            if dry_run:
                _log_dry_run_row(parsed)
                continue

            _upsert_paper_from_csv_row(parsed, stats)

        logger.info(
            "Rows processed: %d, skipped: %d, mailings created: %d, papers created: %d, papers updated: %d",
            stats["rows"],
            stats["skipped"],
            stats["mailings_created"],
            stats["papers_created"],
            stats["papers_updated"],
        )
        logger.info("Done.")
