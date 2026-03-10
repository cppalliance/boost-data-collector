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
    year_val = 0
    if year:
        s = (year if isinstance(year, str) else str(year)).strip()[:4]
        if s.isdigit():
            year_val = int(s)
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
    if not created:
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
    year_val = 0
    if year is not None:
        s = (year if isinstance(year, str) else str(year)).strip()[:4]
        if s.isdigit():
            year_val = int(s)
    WG21Paper.objects.filter(
        paper_id=paper_id,
        year=year_val,
    ).update(is_downloaded=True)
