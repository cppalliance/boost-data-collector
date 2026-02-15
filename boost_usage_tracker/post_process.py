"""
Post-processing for boost_usage_tracker batch include search results.

This module handles per-repository persistence only:
- extract Boost headers from fetched file content,
- map headers to BoostFile,
- register BoostUsage rows.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from boost_library_tracker.models import BoostFile
from boost_usage_tracker.boost_searcher import detect_boost_version_in_repo, extract_boost_includes
from boost_usage_tracker.repo_searcher import RepoSearchResult
from boost_usage_tracker.services import (
    bulk_create_or_update_boost_usage,
    get_active_usages_for_repo,
    get_or_create_boost_external_repo,
    get_or_create_missing_header_usage,
    mark_usages_excepted_bulk,
)
from github_activity_tracker.services import create_or_update_github_file
from github_ops.client import ConnectionException, RateLimitException

if TYPE_CHECKING:
    from github_activity_tracker.models import GitHubRepository

logger = logging.getLogger(__name__)


def _resolve_boost_header(header_path: str):
    """Resolve a Boost include path to a :class:`BoostFile` or *None*."""
    parts = header_path.split("/")
    for i in range(len(parts)):
        suffix = "/".join(parts[i:])
        boost_file = (
            BoostFile.objects
            .filter(github_file__filename__endswith=suffix)
            .select_related("github_file")
            .first()
        )  # pylint: disable=no-member
        if boost_file:
            return boost_file
    return None


def process_single_repo(
    client,
    repo_result: RepoSearchResult,
    file_results_for_repo: list,
    ensure_repo_fn: Callable[[object, RepoSearchResult], "GitHubRepository"],
) -> dict:
    """Persist Boost usage data for one repository from pre-fetched file results.

    The caller provides *file_results_for_repo* from
    ``search_boost_include_files_batch``.
    """
    stats = {
        "usages_created": 0,
        "usages_updated": 0,
        "usages_excepted": 0,
        "missing_header_recorded": 0,
        "boost_used": False,
    }
    repo_full_name = repo_result.full_name

    try:
        github_repo = ensure_repo_fn(client, repo_result)
        is_boost_used = False
        is_embedded = False
        boost_version = ""
        if file_results_for_repo:
            is_embedded, boost_version = detect_boost_version_in_repo(client, repo_full_name)
            is_boost_used = True

        ext_repo, _ = get_or_create_boost_external_repo(
            github_repo,
            boost_version=boost_version or "",
            is_boost_embedded=is_embedded,
            is_boost_used=is_boost_used,
        )

        if not file_results_for_repo:
            return stats

        stats["boost_used"] = is_boost_used
        existing_usages = get_active_usages_for_repo(ext_repo)
        existing_keys = {(u.boost_header_id, u.file_path_id): u for u in existing_usages}
        seen_keys: set[tuple[int | None, int]] = set()

        # Collect (boost_header, file_path, last_commit_date) for bulk upsert; handle missing headers in loop
        bulk_usage_items: list[tuple] = []

        for file_result in file_results_for_repo:
            source_file, _ = create_or_update_github_file(github_repo, file_result.file_path)
            header_paths = extract_boost_includes(file_result.content or "")
            if not header_paths:
                header_paths = list(file_result.boost_headers or [])

            for header_path in header_paths:
                boost_header = _resolve_boost_header(header_path)
                if boost_header is None:
                    _, _, created_tmp = get_or_create_missing_header_usage(
                        repo=ext_repo,
                        file_path=source_file,
                        header_name=header_path,
                        last_commit_date=file_result.commit_date,
                    )
                    if created_tmp:
                        stats["missing_header_recorded"] += 1
                    seen_keys.add((None, source_file.pk))
                    logger.debug(
                        "No BoostFile for header '%s' in %s; recorded in BoostMissingHeaderTmp",
                        header_path,
                        repo_full_name,
                    )
                    continue

                key = (boost_header.pk, source_file.pk)
                seen_keys.add(key)
                bulk_usage_items.append(
                    (boost_header, source_file, file_result.commit_date),
                )

        # Bulk create/update usages (fewer DB round-trips)
        if bulk_usage_items:
            created_count, updated_count = bulk_create_or_update_boost_usage(
                ext_repo, bulk_usage_items
            )
            stats["usages_created"] += created_count
            stats["usages_updated"] += updated_count

        # Bulk mark usages that are no longer detected as excepted
        excepted_ids = [
            u.pk for u in existing_usages
            if (u.boost_header_id, u.file_path_id) not in seen_keys
        ]
        if excepted_ids:
            stats["usages_excepted"] += mark_usages_excepted_bulk(excepted_ids)

    except (ConnectionException, RateLimitException):
        raise
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.warning("Failed post-processing %s: %s", repo_full_name, e)

    return stats
