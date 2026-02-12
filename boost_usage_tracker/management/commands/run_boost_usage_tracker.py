"""
Management command: run_boost_usage_tracker

Two processing units:

1. **monitor_content** (daily):
   Find all repos pushed in a date range with 10+ stars in C++ language.
   For each repo, search for ``#include <boost/…>``, resolve headers to
   BoostFile, and update BoostExternalRepository / BoostUsage tables.

2. **monitor_stars** (monthly):
   Find all C++ repos with 10+ stars created since 2008-04-01.
   For repos *not already tracked* in BoostExternalRepository, check Boost
   usage and update tables.
"""

import logging
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from boost_usage_tracker.models import BoostExternalRepository
from boost_usage_tracker.boost_searcher import (
    BOOST_INCLUDE_SEARCH_BATCH_SIZE,
    search_boost_include_files_batch,
)
from boost_usage_tracker.post_process import process_single_repo
from boost_usage_tracker.repo_searcher import (
    RepoSearchResult,
    search_repos_with_date_splitting,
    CREATION_START_DEFAULT
)
from cppa_user_tracker.services import get_or_create_owner_account
from github_activity_tracker.services import (
    get_or_create_repository,
)
from github_ops import get_github_client
from github_ops.client import ConnectionException, RateLimitException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ensure GitHubRepository from a search result
# ---------------------------------------------------------------------------

def _ensure_github_repo(client, result: RepoSearchResult):
    """Ensure a GitHubRepository (and owner account) exist for *result*.

    Returns the :class:`GitHubRepository` instance.
    """
    owner_name, repo_name = result.full_name.split("/", 1)
    owner_account = get_or_create_owner_account(client, owner_name)

    defaults = {
        "stars": result.stars,
        "description": result.description,
        "forks": 0,
    }
    if result.pushed_at:
        defaults["repo_pushed_at"] = parse_datetime(result.pushed_at)
    if result.created_at:
        defaults["repo_created_at"] = parse_datetime(result.created_at)
    if result.updated_at:
        defaults["repo_updated_at"] = parse_datetime(result.updated_at)

    repo, _ = get_or_create_repository(owner_account, repo_name, **defaults)
    return repo


def _run_boost_search_stage(
    client,
    repo_results: list[RepoSearchResult],
    log_label: str = "",
) -> dict:
    """Shared boost-search stage used by both tasks.

    Steps:
    1) Batch code-search includes for up to 5 repos.
    2) Group file matches by repo.
    3) Run per-repo persistence pipeline.
    """
    totals = {
        "processed": 0,
        "boost_used": 0,
        "usages_created": 0,
        "usages_updated": 0,
        "usages_excepted": 0,
    }

    batch_size = BOOST_INCLUDE_SEARCH_BATCH_SIZE
    for batch_start in range(0, len(repo_results), batch_size):
        batch = repo_results[batch_start : batch_start + batch_size]
        batch_names = [r.full_name for r in batch]
        logger.info(
            "(%d-%d/%d) [%s] Batch code search for %s",
            batch_start + 1,
            batch_start + len(batch),
            len(repo_results),
            log_label or "boost_search",
            batch_names,
        )
        try:
            batch_file_results = search_boost_include_files_batch(client, batch_names)
        except (ConnectionException, RateLimitException) as e:
            logger.error("Rate limit / connection error during batch search: %s", e)
            raise

        by_repo: dict[str, list] = {}
        for fr in batch_file_results:
            by_repo.setdefault(fr.repo_full_name, []).append(fr)

        for repo_result in batch:
            file_results_for_repo = by_repo.get(repo_result.full_name, [])
            logger.info("  [%s] Processing %s", log_label or "boost_search", repo_result.full_name)
            try:
                stats = process_single_repo(
                    client,
                    repo_result,
                    file_results_for_repo=file_results_for_repo,
                    ensure_repo_fn=_ensure_github_repo,
                )
                totals["processed"] += 1
                totals["boost_used"] += int(stats["boost_used"])
                totals["usages_created"] += stats["usages_created"]
                totals["usages_updated"] += stats["usages_updated"]
                totals["usages_excepted"] += stats["usages_excepted"]
            except (ConnectionException, RateLimitException) as e:
                logger.error(
                    "Rate limit / connection error at %s: %s", repo_result.full_name, e
                )
                raise
            except Exception as e:
                logger.warning("Skipping %s due to error: %s", repo_result.full_name, e)

    return totals


# ---------------------------------------------------------------------------
# Task 1: monitor_content (daily)
# ---------------------------------------------------------------------------

def task_monitor_content(
    since: datetime,
    until: datetime,
    min_stars: int,
    dry_run: bool,
) -> None:
    """Daily task: find repos pushed in *[since, until]* and check Boost usage."""
    logger.info(
        "Task: monitor_content (daily) — pushed:%s..%s, stars>%s",
        since.date(),
        until.date(),
        min_stars,
    )
    client = get_github_client(use="scraping")

    repo_results = search_repos_with_date_splitting(
        client, since, until, date_field="pushed", min_stars=min_stars,
    )

    # Deduplicate
    seen: set[str] = set()
    unique: list[RepoSearchResult] = []
    for r in repo_results:
        if r.full_name not in seen:
            seen.add(r.full_name)
            unique.append(r)
    repo_results = unique

    logger.info("Found %d repos pushed in date range", len(repo_results))

    if dry_run:
        for r in repo_results[:20]:
            logger.info("  %s (%s stars)", r.full_name, r.stars)
        if len(repo_results) > 20:
            logger.info("  … and %d more", len(repo_results) - 20)
        return

    totals = _run_boost_search_stage(
        client,
        repo_results,
        log_label="monitor_content",
    )

    logger.info("monitor_content complete: %s", totals)


# ---------------------------------------------------------------------------
# Task 2: monitor_stars (monthly)
# ---------------------------------------------------------------------------

def task_monitor_stars(
    min_stars: int,
    dry_run: bool,
) -> None:
    """Monthly task: find all C++ repos with 10+ stars, process new ones."""
    now = datetime.now(timezone.utc)
    client = get_github_client(use="scraping")

    # Repos already tracked — skip these
    tracked_names: set[str] = set(
        BoostExternalRepository.objects.values_list("repo_name", flat=True)
    )

    start_date = CREATION_START_DEFAULT
    if dry_run:
        start_date = now - timedelta(days=30)

    new_repos: list[RepoSearchResult] = []
    results = search_repos_with_date_splitting(
        client, start_date, now, date_field="created", min_stars=min_stars,
    )
    for r in results:
        if r.full_name not in tracked_names:
            new_repos.append(r)
            tracked_names.add(r.full_name)  # avoid cross-range dups

    logger.info("Found %d new repos not yet tracked", len(new_repos))

    if dry_run:
        for r in new_repos[:20]:
            logger.info("  %s (%s stars)", r.full_name, r.stars)
        if len(new_repos) > 20:
            logger.info("  … and %d more", len(new_repos) - 20)
        return

    totals = _run_boost_search_stage(
        client,
        new_repos,
        log_label="monitor_stars",
    )

    logger.info("monitor_stars complete: %s", totals)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Run Boost Usage Tracker: detect Boost library usage in external C++ "
        "repositories.\n\n"
        "Two tasks:\n"
        "  monitor_content (daily): repos pushed in date range.\n"
        "  monitor_stars  (monthly): all C++ repos with 10+ stars."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--task",
            type=str,
            default=None,
            choices=["monitor_content", "monitor_stars"],
            help=(
                "Run only this task. Default: run both in order "
                "(monitor_content then monitor_stars)."
            ),
        )
        parser.add_argument(
            "--since",
            type=str,
            default=None,
            help="Start date for monitor_content (YYYY-MM-DD). Default: yesterday.",
        )
        parser.add_argument(
            "--until",
            type=str,
            default=None,
            help="End date for monitor_content (YYYY-MM-DD). Default: today.",
        )
        parser.add_argument(
            "--min-stars",
            type=int,
            default=10,
            help="Minimum stars filter (default: 10).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only show what would be done; do not modify the database.",
        )

    def handle(self, *args, **options):
        task_filter = (options["task"] or "").strip().lower()
        dry_run = options["dry_run"]
        min_stars = options["min_stars"]

        now = datetime.now(timezone.utc)
        until = (
            datetime.strptime(options["until"], "%Y-%m-%d").replace(
                tzinfo=timezone.utc,
            )
            if options["until"]
            else now
        )
        since = (
            datetime.strptime(options["since"], "%Y-%m-%d").replace(
                tzinfo=timezone.utc,
            )
            if options["since"]
            else until - timedelta(days=1)
        )

        logger.info(
            "run_boost_usage_tracker: starting (task=%s, dry_run=%s)",
            task_filter or "all",
            dry_run,
        )

        try:
            if not task_filter or task_filter == "monitor_content":
                task_monitor_content(since, until, min_stars, dry_run)

            if not task_filter or task_filter == "monitor_stars":
                task_monitor_stars(min_stars, dry_run)

            logger.info("run_boost_usage_tracker: finished successfully")
        except (ConnectionException, RateLimitException) as e:
            logger.exception(
                "run_boost_usage_tracker failed (rate limit / connection): %s",
                e,
            )
            raise
        except Exception as e:
            logger.exception("run_boost_usage_tracker failed: %s", e)
            raise
