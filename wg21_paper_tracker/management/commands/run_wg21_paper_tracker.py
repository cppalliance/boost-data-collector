"""
Management command for WG21 Paper Tracker.
Runs the pipeline to fetch new mailings, upsert paper metadata in the DB, and optionally
trigger a GitHub repository_dispatch so another repo can download and convert documents.
"""

import logging

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from wg21_paper_tracker.pipeline import run_tracker_pipeline

logger = logging.getLogger(__name__)

GITHUB_DISPATCH_URL = "https://api.github.com/repos/{repo}/dispatches"


def trigger_github_repository_dispatch(
    repo: str,
    event_type: str,
    token: str,
    paper_urls: list[str],
) -> None:
    """POST repository_dispatch with client_payload {"papers": [<url>, ...]}."""
    url = GITHUB_DISPATCH_URL.format(repo=repo.strip())
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token.strip()}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = {
        "event_type": event_type,
        "client_payload": {"papers": paper_urls},
    }
    logger.info(
        "Sending repository_dispatch to %s (event_type=%s, %d URLs).",
        repo,
        event_type,
        len(paper_urls),
    )
    response = requests.post(url, json=body, headers=headers, timeout=30)
    if not response.ok:
        logger.error(
            "GitHub repository_dispatch failed: %s %s",
            response.status_code,
            response.text,
        )
    response.raise_for_status()


class Command(BaseCommand):
    """Run WG21 paper tracker and optionally trigger GitHub repository_dispatch."""

    help = (
        "Run WG21 paper tracker (scrape, DB update) and send new paper URLs via "
        "repository_dispatch when enabled."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only log what would be done; do not run the pipeline or dispatch.",
        )
        parser.add_argument(
            "--from-date",
            dest="from_date",
            metavar="YYYY-MM",
            default=None,
            help=(
                "Process mailings with mailing_date >= YYYY-MM (WG21 / CSV style). "
                "Backfills from that mailing onward; without --to-date, no upper cap."
            ),
        )
        parser.add_argument(
            "--to-date",
            dest="to_date",
            metavar="YYYY-MM",
            default=None,
            help=(
                "Upper bound: mailing_date <= YYYY-MM. With --from-date, inclusive range; "
                "without --from-date, still only mailings newer than DB latest (capped at to)."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        from_date = options.get("from_date")
        to_date = options.get("to_date")
        if from_date is not None:
            from_date = from_date.strip()
            if not from_date:
                from_date = None
        if to_date is not None:
            to_date = to_date.strip()
            if not to_date:
                to_date = None
        if dry_run:
            if from_date or to_date:
                logger.info(
                    "Dry run: skipping pipeline and GitHub dispatch "
                    "(from=%r, to=%r).",
                    from_date,
                    to_date,
                )
            else:
                logger.info("Dry run: skipping pipeline and GitHub dispatch.")
            return

        logger.info("Starting WG21 Paper Tracker...")

        try:
            result = run_tracker_pipeline(
                from_mailing_date=from_date,
                to_mailing_date=to_date,
            )
            n = result.new_paper_count
            logger.info("Recorded %d new paper(s); %d URL(s) for dispatch.", n, n)

            if not n:
                logger.info("No new papers in this run. Skipping GitHub dispatch.")
                return

            repo = getattr(settings, "WG21_GITHUB_DISPATCH_REPO", "") or ""
            token = getattr(settings, "WG21_GITHUB_DISPATCH_TOKEN", "") or ""
            enabled = getattr(settings, "WG21_GITHUB_DISPATCH_ENABLED", False)
            event_type = getattr(
                settings,
                "WG21_GITHUB_DISPATCH_EVENT_TYPE",
                "wg21_papers_convert",
            )

            if not enabled or not repo or not token:
                logger.warning(
                    "Skipping GitHub dispatch: set WG21_GITHUB_DISPATCH_ENABLED=True "
                    "and configure WG21_GITHUB_DISPATCH_REPO and "
                    "WG21_GITHUB_DISPATCH_TOKEN."
                )
                return
            try:
                trigger_github_repository_dispatch(
                    repo,
                    event_type,
                    token,
                    list(result.new_paper_urls),
                )
                logger.info("repository_dispatch sent successfully.")
            except Exception:
                logger.exception("Failed to send repository_dispatch.")
                raise

        except ValueError as e:
            raise CommandError(str(e)) from e
        except Exception as e:
            logger.exception("WG21 Paper Tracker failed: %s", e)
            raise
