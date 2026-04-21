"""Django management command - sync using DiscordChatExporter CLI with user token."""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone as django_timezone

from core.utils.datetime_parsing import parse_iso_datetime
from discord_activity_tracker.github_publish import push_discord_markdown_to_github
from discord_activity_tracker.models import DiscordChannel, DiscordServer
from discord_activity_tracker.sync.chat_exporter import (
    export_guild_to_json,
    parse_exported_json,
)
from discord_activity_tracker.sync.export import export_and_push
from discord_activity_tracker.sync.importer import persist_exporter_channel_payloads
from discord_activity_tracker.workspace import get_raw_dir

logger = logging.getLogger(__name__)

PINECONE_NAMESPACE_ENV_KEY = "DISCORD_PINECONE_NAMESPACE"


def _aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if django_timezone.is_naive(dt):
        return django_timezone.make_aware(dt, django_timezone.utc)
    return dt


def _run_discord_pinecone_sync(*, dry_run: bool) -> None:
    """Upsert Discord messages to Pinecone via run_cppa_pinecone_sync."""
    from django.core.management import call_command

    app_type = (getattr(settings, "DISCORD_PINECONE_APP_TYPE", "") or "").strip()
    namespace = (getattr(settings, "DISCORD_PINECONE_NAMESPACE", "") or "").strip()
    if not app_type:
        logger.warning(
            "Pinecone sync skipped: DISCORD_PINECONE_APP_TYPE is empty (settings/env)."
        )
        return
    if not namespace:
        logger.warning(
            "Pinecone sync skipped: namespace is empty (set %s or Django setting).",
            PINECONE_NAMESPACE_ENV_KEY,
        )
        return
    if dry_run:
        logger.info("dry-run would run Pinecone sync for Discord messages")
        return
    try:
        call_command(
            "run_cppa_pinecone_sync",
            app_type=app_type,
            namespace=namespace,
            preprocessor=(
                "discord_activity_tracker.preprocessors.discord_preprocessor."
                "preprocess_discord_for_pinecone"
            ),
        )
        logger.info(
            "Pinecone sync completed (app_type=%s, namespace=%s)",
            app_type,
            namespace,
        )
    except Exception as exc:
        logger.warning(
            "Pinecone sync skipped/failed (run_cppa_pinecone_sync unavailable or errored): %s",
            exc,
        )


class Command(BaseCommand):
    help = (
        "Run Discord Activity Tracker using DiscordChatExporter CLI (user token method). "
        "After markdown export, optionally push to DISCORD_MARKDOWN_REPO_* and run Pinecone sync."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview actions without writing to the database (no markdown writes in export steps).",
        )
        parser.add_argument(
            "--task",
            type=str,
            default="all",
            choices=["sync", "export", "all", "import-only"],
            help="Task to run: sync, export, all, or import-only (default: all).",
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
            help="Number of months to export to markdown (default: 12).",
        )
        parser.add_argument(
            "--active-days",
            type=int,
            default=30,
            help="Number of days to consider a channel active (default: 30).",
        )
        parser.add_argument(
            "--days-back",
            type=int,
            default=30,
            help="Number of days back to sync messages (default: 30, 0 for all history).",
        )
        parser.add_argument(
            "--skip-github-push",
            action="store_true",
            help="Skip uploading markdown to DISCORD_MARKDOWN_REPO_* after export.",
        )
        parser.add_argument(
            "--skip-pinecone",
            action="store_true",
            help="Skip run_cppa_pinecone_sync for Discord messages.",
        )
        parser.add_argument(
            "--skip-sync",
            action="store_true",
            help="Skip exportguild → DB sync when --task is all or sync.",
        )
        parser.add_argument(
            "--skip-markdown-export",
            action="store_true",
            help="Skip writing markdown to DISCORD_CONTEXT_REPO_PATH (export / all / import-only).",
        )
        parser.add_argument(
            "--since",
            "--from-date",
            "--start-time",
            type=str,
            default=None,
            dest="since",
            help="Sync window start (YYYY-MM-DD or ISO-8601); passed to exportguild --after. "
            "--from-date and --start-time are deprecated aliases for --since.",
        )
        parser.add_argument(
            "--until",
            "--to-date",
            "--end-time",
            type=str,
            default=None,
            dest="until",
            help="Sync window end (same formats as --since); passed to exportguild --before. "
            "--to-date and --end-time are deprecated aliases for --until.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        task = options["task"]
        full_sync = options["full_sync"]
        months = options["months"]
        active_days = options["active_days"]
        days_back = options["days_back"]
        skip_github_push = options["skip_github_push"]
        skip_pinecone = options["skip_pinecone"]
        skip_sync = options["skip_sync"]
        skip_markdown_export = options["skip_markdown_export"]

        try:
            since_dt = parse_iso_datetime(options.get("since"))
            until_dt = parse_iso_datetime(options.get("until"))
        except ValueError as e:
            raise CommandError(str(e)) from e
        if since_dt and until_dt and since_dt > until_dt:
            logger.warning(
                "Invalid date range: since (%s) after until (%s); ignoring both",
                since_dt.isoformat(),
                until_dt.isoformat(),
            )
            since_dt = until_dt = None

        since_aware = _aware_utc(since_dt)
        until_aware = _aware_utc(until_dt)

        try:
            user_token = getattr(settings, "DISCORD_USER_TOKEN", None)
            guild_id = getattr(settings, "DISCORD_SERVER_ID", None)
            context_repo_path = getattr(settings, "DISCORD_CONTEXT_REPO_PATH", None)

            if not user_token:
                self.stdout.write(self.style.ERROR("DISCORD_USER_TOKEN not configured"))
                self.stdout.write(
                    "Set it in .env file. See DiscordChatExporter docs for token extraction."
                )
                return

            if not guild_id:
                self.stdout.write(self.style.ERROR("DISCORD_SERVER_ID not configured"))
                return

            markdown_wanted = (task in ("export", "all")) or (
                task == "import-only" and not skip_markdown_export
            )
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
                    self.style.WARNING("--skip-sync: skipping exportguild → DB sync")
                )

            if run_sync:
                self._sync_messages(
                    dry_run=dry_run,
                    user_token=user_token,
                    guild_id=guild_id,
                    full_sync=full_sync,
                    days_back=days_back,
                    since_override=since_aware,
                    until_cutoff=until_aware,
                )

            if task == "import-only":
                self._import_json_files(
                    dry_run=dry_run,
                    guild_id=guild_id,
                    since_override=since_aware,
                    until_cutoff=until_aware,
                )

            export_ok = False
            if markdown_wanted:
                export_ok = self._export_markdown(
                    dry_run=dry_run,
                    guild_id=guild_id,
                    context_repo_path=context_repo_path,
                    months=months,
                    active_days=active_days,
                )
            elif task == "import-only" and skip_markdown_export:
                self.stdout.write(
                    self.style.WARNING(
                        "--skip-markdown-export: skipping markdown export after import-only"
                    )
                )

            if (
                markdown_wanted
                and context_repo_path
                and not skip_github_push
            ):
                self.stdout.write("\n=== Uploading markdown to GitHub ===")
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            "DRY RUN — would upload markdown folder to "
                            "DISCORD_MARKDOWN_REPO_*"
                        )
                    )
                elif export_ok:
                    push_discord_markdown_to_github(context_repo_path)
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "Skipping GitHub upload (no markdown files exported this run)"
                        )
                    )

            if not skip_pinecone:
                self.stdout.write("\n=== Pinecone sync (Discord) ===")
                _run_discord_pinecone_sync(dry_run=dry_run)
            else:
                logger.info("skipping Pinecone (--skip-pinecone)")

            self.stdout.write(self.style.SUCCESS("✓ Discord exporter completed"))

        except Exception as e:
            logger.exception("Discord exporter failed: %s", e)
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            raise

    def _sync_messages(
        self,
        dry_run: bool,
        user_token: str,
        guild_id: int,
        full_sync: bool,
        days_back: int,
        since_override: Optional[datetime],
        until_cutoff: Optional[datetime],
    ):
        """Export messages via CLI and persist to database."""
        self.stdout.write("\n=== Syncing Messages using DiscordChatExporter ===")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no database writes"))

        temp_dir = get_raw_dir()

        try:
            server = DiscordServer.objects.filter(server_id=guild_id).first()

            after_date = None
            days_back_date = (
                (django_timezone.now() - timedelta(days=days_back))
                if days_back > 0
                else None
            )

            if full_sync:
                after_date = days_back_date
                if after_date:
                    self.stdout.write(
                        f"Full sync - last {days_back} days from: {after_date}"
                    )
                else:
                    self.stdout.write("Full sync - fetching all messages")
            elif server:
                earliest_sync = (
                    DiscordChannel.objects.filter(server=server)
                    .exclude(last_synced_at__isnull=True)
                    .order_by("last_synced_at")
                    .first()
                )

                sync_date = earliest_sync.last_synced_at if earliest_sync else None

                if sync_date and days_back_date:
                    after_date = min(sync_date, days_back_date)
                    self.stdout.write(f"Syncing from: {after_date}")
                elif sync_date:
                    after_date = sync_date
                    self.stdout.write(f"Incremental sync from: {after_date}")
                elif days_back_date:
                    after_date = days_back_date
                    self.stdout.write(
                        f"First sync - last {days_back} days from: {after_date}"
                    )
                else:
                    self.stdout.write("First sync - fetching all messages")
            else:
                after_date = days_back_date
                if after_date:
                    self.stdout.write(
                        f"First sync - last {days_back} days from: {after_date}"
                    )
                else:
                    self.stdout.write("First sync - fetching all messages")

            if since_override is not None:
                if after_date is None:
                    after_date = since_override
                else:
                    after_date = max(after_date, since_override)
                self.stdout.write(f"  --since lower bound: {after_date}")

            json_files = export_guild_to_json(
                user_token=user_token,
                guild_id=guild_id,
                output_dir=temp_dir,
                after_date=after_date,
                before_date=until_cutoff,
            )

            self.stdout.write(f"Exported {len(json_files)} channel files")

            if dry_run:
                for json_path in json_files:
                    data = parse_exported_json(json_path)
                    ch = data.get("channel", {})
                    msg_count = len(data.get("messages", []))
                    self.stdout.write(f"  #{ch.get('name', '?')}: {msg_count} messages")
                return

            for i, json_path in enumerate(json_files, 1):
                try:
                    data = parse_exported_json(json_path)
                    channel_data = {
                        "guild": data.get("guild", {}),
                        "channel": data.get("channel", {}),
                        "messages": data.get("messages", []),
                    }
                    ch_name = channel_data["channel"].get("name", "?")
                    msg_count = len(channel_data["messages"])
                    self.stdout.write(
                        f"  [{i}/{len(json_files)}] #{ch_name}: {msg_count} messages"
                    )
                    asyncio.run(
                        persist_exporter_channel_payloads(
                            [channel_data],
                            expected_guild_id=guild_id,
                        )
                    )
                    json_path.unlink()
                except Exception as e:
                    logger.error(f"Failed to process {json_path.name}: {e}")
                    continue

            self.stdout.write("Done persisting all channels")

        except Exception as e:
            logger.exception(f"Sync failed: {e}")
            raise

    def _import_json_files(
        self,
        dry_run: bool,
        guild_id: int,
        since_override: Optional[datetime],
        until_cutoff: Optional[datetime],
    ):
        """Import pre-exported JSON files from raw/ into the database."""
        self.stdout.write("\n=== Importing JSON Files ===")

        temp_dir = get_raw_dir()

        json_files = sorted(temp_dir.glob("*.json"))
        if not json_files:
            self.stdout.write(self.style.ERROR(f"No JSON files found in {temp_dir}"))
            return

        self.stdout.write(f"Found {len(json_files)} JSON files")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no database writes"))
            for f in json_files:
                self.stdout.write(f"  {f.name}")
            return

        parsed_data = []
        for json_path in json_files:
            try:
                data = parse_exported_json(json_path)
                if since_override is not None or until_cutoff is not None:
                    msgs = data.get("messages") or []
                    if msgs:
                        from discord_activity_tracker.sync.utils import parse_datetime

                        times = []
                        for m in msgs:
                            t = parse_datetime(m.get("timestamp") or m.get("created_at"))
                            if t:
                                times.append(t)
                        if times:
                            lo, hi = min(times), max(times)
                            if since_override is not None and hi < since_override:
                                continue
                            if until_cutoff is not None and lo > until_cutoff:
                                continue
                parsed_data.append(
                    {
                        "guild": data.get("guild", {}),
                        "channel": data.get("channel", {}),
                        "messages": data.get("messages", []),
                        "file_path": json_path,
                    }
                )
                self.stdout.write(
                    f"  Parsed {json_path.name}: {len(data.get('messages', []))} messages"
                )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"  Skipping {json_path.name}: {e}")
                )
                continue

        self.stdout.write(f"Importing {len(parsed_data)} channels...")

        asyncio.run(
            persist_exporter_channel_payloads(
                parsed_data,
                expected_guild_id=guild_id,
            )
        )

        self.stdout.write(self.style.SUCCESS(f"✓ Imported {len(parsed_data)} channels"))

    def _export_markdown(
        self,
        dry_run: bool,
        guild_id: int,
        context_repo_path: Path,
        months: int,
        active_days: int,
    ) -> bool:
        """Export to markdown files. Returns True if at least one file was written."""
        self.stdout.write("\n=== Exporting to Markdown ===")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no file writes"))
            return False

        try:
            server = DiscordServer.objects.get(server_id=guild_id)
        except DiscordServer.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f"Server {guild_id} not found in database. Run sync first."
                )
            )
            return False

        success = export_and_push(
            context_repo_path=context_repo_path,
            server=server,
            months_back=months,
            active_days=active_days,
            auto_commit=False,
        )

        if success:
            self.stdout.write(self.style.SUCCESS(f"✓ Exported to {context_repo_path}"))
        else:
            self.stdout.write(self.style.WARNING("No files exported"))
        return bool(success)
