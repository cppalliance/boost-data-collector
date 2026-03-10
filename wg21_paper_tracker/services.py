"""
Database logic for WG21 Paper Tracker.
"""

from typing import Optional

from django.db import transaction

from cppa_user_tracker.services import get_or_create_wg21_paper_author_profile
from wg21_paper_tracker.models import WG21Mailing, WG21Paper, WG21PaperAuthor


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
    year: int | None = None,
) -> tuple[WG21Paper, bool]:
    paper_id = (paper_id or "").strip().lower()
    year_val = None
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
        if year_val is not None and paper.year != year_val:
            paper.year = year_val
            updated = True
        if updated:
            paper.save()

    if author_names:
        for name in author_names:
            profile, _ = get_or_create_wg21_paper_author_profile(name)
            WG21PaperAuthor.objects.get_or_create(
                paper=paper,
                profile=profile,
            )

    return paper, created


def mark_paper_downloaded(paper_id: str):
    paper_id = (paper_id or "").strip().lower()
    WG21Paper.objects.filter(paper_id=paper_id).update(is_downloaded=True)
