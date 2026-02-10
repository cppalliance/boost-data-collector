"""
Management command: run_cppa_pinecone_sync

Runs Pinecone sync for one or all registered source types.
This command is meant for manual or scheduled invocation; normally other
apps call ``cppa_pinecone_sync.sync.sync_to_pinecone()`` directly.

Usage:
    python manage.py run_cppa_pinecone_sync
    python manage.py run_cppa_pinecone_sync --type slack
"""

import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Run CPPA Pinecone Sync. Normally other apps call sync_to_pinecone() directly; "
        "this command is for manual or scheduled runs."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            type=str,
            default=None,
            help="Run sync for a single type only (e.g. 'slack', 'mailing_list', 'wg21').",
        )

    def handle(self, *args, **options):
        sync_type = (options["type"] or "").strip() or None
        logger.info(
            "run_cppa_pinecone_sync: starting (type=%s)",
            sync_type or "all",
        )

        try:
            # Stub: In production, iterate registered (type, namespace, preprocess_fn)
            # tuples and call sync_to_pinecone for each.  For now this command logs
            # and exits successfully; the real entry point is sync_to_pinecone() called
            # by other apps.
            self.stdout.write(
                self.style.SUCCESS(
                    "CPPA Pinecone Sync completed (stub — other apps call sync_to_pinecone() directly)."
                )
            )
            logger.info("run_cppa_pinecone_sync: finished successfully")
        except Exception as e:
            logger.exception("run_cppa_pinecone_sync failed: %s", e)
            raise
