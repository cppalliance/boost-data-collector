"""
Database logic for WG21 Paper Tracker.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from django.db import transaction

from cppa_user_tracker.services import get_or_create_wg21_paper_author_profile
from wg21_paper_tracker.models import WG21Mailing, WG21Paper, WG21PaperAuthor

if TYPE_CHECKING:
    from cppa_user_tracker.models import WG21PaperAuthorProfile


def _normalize_year(year: int | str | None) -> int:
    """Return a 4-digit year as int, or 0 if missing/invalid."""
    if year is None:
        return 0
    if isinstance(year, int):
        return year if 0 < year <= 9999 else 0
    s = str(year).strip()[:4]
    return int(s) if s.isdigit() else 0


@transaction.atomic
def get_or_create_mailing(mailing_date: str, title: str) -> tuple[WG21Mailing, bool]:
    mailing, created = WG21Mailing.objects.get_or_create(
        mailing_date=mailing_date, defaults={"title": title}
    )
    if not created and mailing.title != title:
        mailing.title = title
        mailing.save(update_fields=["title", "updated_at"])
    return mailing, created


@transaction.atomic
def get_or_create_paper(
    paper_id: str,
    url: str,
    title: str,
    document_date: Optional[str],
    mailing: WG21Mailing,
    subgroup: str = "",
    author_names: Optional[list[str]] = None,
    author_emails: Optional[list[str]] = None,
    year: int | None = None,
) -> tuple[WG21Paper, bool]:
    paper_id = (paper_id or "").strip().lower()
    year_val = _normalize_year(year)

    def _update_paper(paper: WG21Paper) -> bool:
        updated = False
        if paper.url != url:
            paper.url = url
            updated = True
        if paper.title != title:
            paper.title = title
            updated = True
        if paper.document_date != document_date:
            paper.document_date = document_date
            updated = True
        if paper.mailing_id != mailing.id:
            paper.mailing = mailing
            updated = True
        if paper.subgroup != subgroup:
            paper.subgroup = subgroup
            updated = True
        if paper.year != year_val:
            paper.year = year_val
            updated = True
        if updated:
            paper.save()
        return updated

    if year_val > 0:
        # Prefer exact (paper_id, year); else promote placeholder (paper_id, 0) to real year
        paper = WG21Paper.objects.filter(paper_id=paper_id, year=year_val).first()
        if paper:
            _update_paper(paper)
            created = False
        else:
            placeholder = WG21Paper.objects.filter(paper_id=paper_id, year=0).first()
            if placeholder:
                placeholder.url = url
                placeholder.title = title
                placeholder.document_date = document_date
                placeholder.mailing = mailing
                placeholder.subgroup = subgroup
                placeholder.year = year_val
                placeholder.save()
                paper = placeholder
                created = False
            else:
                paper, created = WG21Paper.objects.get_or_create(
                    paper_id=paper_id,
                    year=year_val,
                    defaults={
                        "url": url,
                        "title": title,
                        "document_date": document_date,
                        "mailing": mailing,
                        "subgroup": subgroup,
                    },
                )
    else:
        paper, created = WG21Paper.objects.get_or_create(
            paper_id=paper_id,
            year=0,
            defaults={
                "url": url,
                "title": title,
                "document_date": document_date,
                "mailing": mailing,
                "subgroup": subgroup,
            },
        )
        if not created:
            _update_paper(paper)

    if author_names:
        emails = author_emails or []
        for i, name in enumerate(author_names):
            email = emails[i] if i < len(emails) else None
            profile, _ = get_or_create_wg21_paper_author_profile(name, email=email)
            get_or_create_paper_author(paper, profile, i + 1)

    return paper, created


def get_or_create_paper_author(
    paper: WG21Paper,
    profile: WG21PaperAuthorProfile,
    author_order: int,
) -> tuple[WG21PaperAuthor, bool]:
    """Get or create a WG21PaperAuthor link for (paper, profile), with author_order (1-based).
    Updates author_order on existing link if it differs.
    """
    link, link_created = WG21PaperAuthor.objects.get_or_create(
        paper=paper,
        profile=profile,
        defaults={"author_order": author_order},
    )
    if not link_created and link.author_order != author_order:
        link.author_order = author_order
        link.save(update_fields=["author_order"])
    return link, link_created


def mark_paper_downloaded(paper_id: str, year: int | None = None):
    paper_id = (paper_id or "").strip().lower()
    if year is None:
        raise ValueError("year is required; pass 0 explicitly for placeholder papers")
    year_val = _normalize_year(year)
    WG21Paper.objects.filter(
        paper_id=paper_id,
        year=year_val,
    ).update(is_downloaded=True)
