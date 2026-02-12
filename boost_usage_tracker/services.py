"""
Service layer for boost_usage_tracker.

All creates/updates/deletes for this app's models must go through functions here.
See docs/Contributing.md for the project-wide rule.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from .models import BoostExternalRepository, BoostMissingHeaderTmp, BoostUsage

if TYPE_CHECKING:
    from boost_library_tracker.models import BoostFile
    from github_activity_tracker.models import GitHubFile, GitHubRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BoostExternalRepository
# ---------------------------------------------------------------------------

def get_or_create_boost_external_repo(
    github_repository: "GitHubRepository",
    boost_version: str = "",
    is_boost_embedded: bool = False,
    is_boost_used: bool = False,
) -> tuple[BoostExternalRepository, bool]:
    """Get or create BoostExternalRepository for a GitHubRepository (multi-table inheritance).

    Creates only the child row via raw SQL to avoid NOT NULL errors on corrupt
    parent rows (same pattern as ``boost_library_tracker.services``).

    If the row already exists the mutable flags are updated.
    """
    from django.db import IntegrityError, connection
    from django.utils import timezone

    existing = BoostExternalRepository.objects.filter(
        githubrepository_ptr_id=github_repository.pk,
    ).first()

    if existing is not None:
        update_fields: list[str] = []
        if boost_version and existing.boost_version != boost_version:
            existing.boost_version = boost_version
            update_fields.append("boost_version")
        if existing.is_boost_embedded != is_boost_embedded:
            existing.is_boost_embedded = is_boost_embedded
            update_fields.append("is_boost_embedded")
        if existing.is_boost_used != is_boost_used:
            existing.is_boost_used = is_boost_used
            update_fields.append("is_boost_used")
        if update_fields:
            existing.updated_at = timezone.now()
            update_fields.append("updated_at")
            existing.save(update_fields=update_fields)
        return existing, False

    try:
        now = timezone.now()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO boost_usage_tracker_boostexternalrepository
                    (githubrepository_ptr_id, boost_version, is_boost_embedded,
                     is_boost_used, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                [
                    github_repository.pk,
                    boost_version,
                    is_boost_embedded,
                    is_boost_used,
                    now,
                    now,
                ],
            )
    except IntegrityError:
        existing = BoostExternalRepository.objects.get(pk=github_repository.pk)
        return existing, False

    return BoostExternalRepository.objects.get(pk=github_repository.pk), True


def update_boost_external_repo(
    ext_repo: BoostExternalRepository,
    boost_version: Optional[str] = None,
    is_boost_embedded: Optional[bool] = None,
    is_boost_used: Optional[bool] = None,
) -> BoostExternalRepository:
    """Update mutable fields on an existing BoostExternalRepository."""
    update_fields: list[str] = []
    if boost_version is not None and ext_repo.boost_version != boost_version:
        ext_repo.boost_version = boost_version
        update_fields.append("boost_version")
    if is_boost_embedded is not None and ext_repo.is_boost_embedded != is_boost_embedded:
        ext_repo.is_boost_embedded = is_boost_embedded
        update_fields.append("is_boost_embedded")
    if is_boost_used is not None and ext_repo.is_boost_used != is_boost_used:
        ext_repo.is_boost_used = is_boost_used
        update_fields.append("is_boost_used")
    if update_fields:
        ext_repo.save(update_fields=update_fields + ["updated_at"])
    return ext_repo


# ---------------------------------------------------------------------------
# BoostUsage
# ---------------------------------------------------------------------------

def create_or_update_boost_usage(
    repo: BoostExternalRepository,
    boost_header: "BoostFile",
    file_path: "GitHubFile",
    last_commit_date: Optional[datetime] = None,
) -> tuple[BoostUsage, bool]:
    """Create or update a BoostUsage record.

    If the record already exists its ``last_commit_date`` is refreshed and
    ``excepted_at`` is cleared (re-detected).
    """
    usage, created = BoostUsage.objects.get_or_create(
        repo=repo,
        boost_header=boost_header,
        file_path=file_path,
        defaults={"last_commit_date": last_commit_date},
    )
    if not created:
        changed = False
        if last_commit_date and usage.last_commit_date != last_commit_date:
            usage.last_commit_date = last_commit_date
            changed = True
        if usage.excepted_at is not None:
            usage.excepted_at = None
            changed = True
        if changed:
            usage.save(update_fields=["last_commit_date", "excepted_at", "updated_at"])
    return usage, created


def mark_usage_excepted(usage: BoostUsage) -> BoostUsage:
    """Mark a BoostUsage record as excepted (include no longer detected)."""
    if usage.excepted_at is None:
        usage.excepted_at = date.today()
        usage.save(update_fields=["excepted_at", "updated_at"])
    return usage


def get_active_usages_for_repo(
    repo: BoostExternalRepository,
) -> list[BoostUsage]:
    """Return all active (non-excepted) BoostUsage records for *repo*."""
    return list(
        BoostUsage.objects.filter(repo=repo, excepted_at__isnull=True)
        .select_related("boost_header", "file_path")
    )


def get_or_create_missing_header_usage(
    repo: BoostExternalRepository,
    file_path: "GitHubFile",
    header_name: str,
    last_commit_date: Optional[datetime] = None,
) -> tuple[BoostUsage, BoostMissingHeaderTmp, bool]:
    """Get or create a placeholder BoostUsage (boost_header=null) and a BoostMissingHeaderTmp.

    Used when header_name is not yet in BoostFile/GitHubFile. Returns (usage, tmp, created_tmp).
    """
    usage, _ = BoostUsage.objects.get_or_create(
        repo=repo,
        boost_header=None,
        file_path=file_path,
        defaults={"last_commit_date": last_commit_date},
    )
    if not _ and last_commit_date and usage.last_commit_date != last_commit_date:
        usage.last_commit_date = last_commit_date
        usage.save(update_fields=["last_commit_date", "updated_at"])
    tmp, created_tmp = BoostMissingHeaderTmp.objects.get_or_create(
        usage=usage,
        header_name=header_name,
    )
    return usage, tmp, created_tmp
