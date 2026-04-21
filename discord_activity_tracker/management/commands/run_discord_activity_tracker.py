"""Django management command - sync messages and export to markdown (Discord bot token)."""

import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.utils.datetime_parsing import parse_iso_datetime
from discord_activity_tracker.models import DiscordChannel, DiscordServer
from discord_activity_tracker.sync.export import export_and_push
from discord_activity_tracker.sync.messages import sync_all_channels

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Run Discord Activity Tracker: sync messages (Discord API / bot token) and export to markdown. "
        "Use --since/--until to bound the API sync window when supported. "
        "Markdown export still uses active channel filters (months / active-days)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview actions without executing them (no database writes).",
        )
        parser.add_argument(
            "--task",
            type=str,
            default="all",
            choices=["sync", "export", "all"],
            help="Run sync, export markdown, or both (default: all).",
        )
        parser.add_argument(
            "--skip-sync",
            action="store_true",
            help="Skip Discord API message sync (with --task all or sync).",
        )
        parser.add_argument(
            "--skip-markdown-export",
            action="store_true",
            help="Skip markdown export (with --task all or export).",
        )
        parser.add_argument(
            "--full-sync",
            action="store_true",
            help="Sync all messages (ignore last_synced_at).",
        )
        parser.add_argument(
            "--months",
            type=int,
            default=12,
            help="Number of months to export (default: 12).",
        )
        parser.add_argument(
            "--active-days",
            type=int,
            default=30,
            help="Number of days to consider a channel active (default: 30).",
        )
        parser.add_argument(
            "--since",
            "--from-date",
            "--start-time",
            type=str,
            default=None,
            dest="since",
            help="Lower bound for message sync (YYYY-MM-DD or ISO-8601). Passed to sync_all_channels. "
            "--from-date and --start-time are deprecated aliases for --since.",
        )
        parser.add_argument(
            "--until",
            "--to-date",
            "--end-time",
            type=str,
            default=None,
            dest="until",
            help="Upper bound for message sync (same formats as --since). "
            "Note: the Discord client currently fetches forward from the sync cursor; "
            "this value is passed for API consistency where supported. "
            "--to-date and --end-time are deprecated aliases for --until.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        task = options["task"]
        skip_sync = options["skip_sync"]
        skip_markdown_export = options["skip_markdown_export"]
        full_sync = options["full_sync"]
        months = options["months"]
        active_days = options["active_days"]

        try:
            since_dt = parse_iso_datetime(options.get("since"))
            until_dt = parse_iso_datetime(options.get("until"))
        except ValueError as e:
            raise CommandError(str(e)) from e
        if since_dt and until_dt and since_dt > until_dt:
            logger.warning(
                "Invalid date range: since after until; ignoring both for sync window"
            )
            since_dt = until_dt = None

        try:
            token = getattr(settings, "DISCORD_TOKEN", None)
            guild_id = getattr(settings, "DISCORD_SERVER_ID", None)
            context_repo_path = getattr(settings, "DISCORD_CONTEXT_REPO_PATH", None)

            if not token:
                self.stdout.write(self.style.ERROR("DISCORD_TOKEN not configured"))
                return

            if not guild_id:
                self.stdout.write(self.style.ERROR("DISCORD_SERVER_ID not configured"))
                return

            markdown_wanted = (task in ("export", "all")) and not skip_markdown_export
            if markdown_wanted and not context_repo_path:
                self.stdout.write(
                    self.style.ERROR("DISCORD_CONTEXT_REPO_PATH not configured")
                )
                return

            context_repo_path = (
                Path(context_repo_path).resolve() if context_repo_path else None
            )
            guild_id = int(guild_id)

            run_sync = task in ("sync", "all") and not skip_sync
            if skip_sync and task in ("sync", "all"):
                self.stdout.write(
                    self.style.WARNING("--skip-sync: skipping Discord API message sync")
                )

            if run_sync:
                self._task_sync_messages(
                    dry_run=dry_run,
                    token=token,
                    guild_id=guild_id,
                    full_sync=full_sync,
                    active_days=active_days,
                    since_date=since_dt,
                )

            if markdown_wanted:
                self._task_export_markdown(
                    dry_run=dry_run,
                    guild_id=guild_id,
                    context_repo_path=context_repo_path,
                    months=months,
                    active_days=active_days,
                )
            elif task in ("export", "all") and skip_markdown_export:
                self.stdout.write(
                    self.style.WARNING(
                        "--skip-markdown-export: skipping markdown export step"
                    )
                )

            self.stdout.write(
                self.style.SUCCESS("✓ Discord activity tracker completed")
            )

        except Exception as e:
            logger.exception("Discord activity tracker failed: %s", e)
            raise

    def _task_sync_messages(
        self,
        dry_run: bool,
        token: str,
        guild_id: int,
        full_sync: bool,
        active_days: int,
        since_date,
    ):
        """Sync messages from Discord API to database."""
        self.stdout.write("Task 1: Syncing Discord messages...")

        if dry_run:
            try:
                server = DiscordServer.objects.get(server_id=guild_id)
                channels = DiscordChannel.objects.filter(server=server)

                if not full_sync:
                    from datetime import timedelta

                    from django.utils import timezone

                    cutoff = timezone.now() - timedelta(days=active_days)
                    channels = channels.filter(last_activity_at__gte=cutoff)

                self.stdout.write(f"  Would sync {channels.count()} channels")
                if since_date:
                    self.stdout.write(f"  Would use sync lower bound: {since_date}")
                for channel in channels:
                    last_sync = channel.last_synced_at or "never"
                    self.stdout.write(
                        f"    - #{channel.channel_name} (last sync: {last_sync})"
                    )

            except DiscordServer.DoesNotExist:
                self.stdout.write(f"  Would sync server {guild_id} (first time)")

            return

        logger.info("Syncing messages from Discord guild %s", guild_id)

        sync_all_channels(
            token=token,
            guild_id=guild_id,
            since_date=since_date,
            full_sync=full_sync,
            active_only=not full_sync,
            active_days=active_days,
        )

        server = DiscordServer.objects.get(server_id=guild_id)
        total_channels = DiscordChannel.objects.filter(server=server).count()
        total_messages = sum(
            channel.messages.count()
            for channel in DiscordChannel.objects.filter(server=server)
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ Synced {total_channels} channels, {total_messages} total messages"
            )
        )

    def _task_export_markdown(
        self,
        dry_run: bool,
        guild_id: int,
        context_repo_path: Path,
        months: int,
        active_days: int,
    ):
        """Export to markdown files and push to context repo."""
        self.stdout.write("Task 2: Exporting to markdown...")

        try:
            server = DiscordServer.objects.get(server_id=guild_id)
        except DiscordServer.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    "  Server not found in database. Run sync task first."
                )
            )
            return

        if dry_run:
            from datetime import timedelta

            from django.utils import timezone

            cutoff = timezone.now() - timedelta(days=active_days)
            channels = DiscordChannel.objects.filter(
                server=server, last_activity_at__gte=cutoff
            )

            self.stdout.write(
                f"  Would export {channels.count()} active channels to {context_repo_path}"
            )
            self.stdout.write(f"  Months back: {months}")
            self.stdout.write(f"  Active days threshold: {active_days}")

            for channel in channels:
                self.stdout.write(f"    - #{channel.channel_name}")

            return

        logger.info("Exporting to markdown: %s", context_repo_path)

        success = export_and_push(
            context_repo_path=context_repo_path,
            server=server,
            months_back=months,
            active_days=active_days,
            auto_commit=False,
        )

        if success:
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Exported to {context_repo_path}")
            )
        else:
            self.stdout.write(self.style.WARNING("  ⚠ Export failed"))
