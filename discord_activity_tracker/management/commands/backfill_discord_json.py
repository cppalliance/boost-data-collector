"""Import historical DiscordChatExporter JSON (per-day / chunk layout) into the database."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.utils.datetime_parsing import parse_iso_datetime
from discord_activity_tracker.sync.backfill_paths import (
    iter_discussion_json_files,
    json_path_in_date_window,
)
from discord_activity_tracker.sync.chat_exporter import parse_exported_json
from discord_activity_tracker.sync.importer import persist_exporter_channel_payloads
from discord_activity_tracker.workspace import get_discussion_export_dir

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Backfill Discord messages from DiscordChatExporter JSON files (e.g. "
        "workspace/discord_activity_tracker/Discussion - c-cpp-discussion/). "
        "Processes one file at a time. Use --dry-run to list files only."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default=None,
            help=(
                "Root directory to scan (default: workspace/discord_activity_tracker/"
                "Discussion - c-cpp-discussion/)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List files that would be imported; do not write to the database.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            metavar="N",
            help="Process at most N JSON files (0 = no limit).",
        )
        parser.add_argument(
            "--guild-id",
            type=int,
            default=None,
            help="If set, skip JSON whose guild id does not match (default: DISCORD_SERVER_ID).",
        )
        parser.add_argument(
            "--since",
            "--from-date",
            "--start-time",
            type=str,
            default=None,
            dest="since",
            help="Only include files whose day/chunk range overlaps this date (YYYY-MM-DD or ISO). "
            "Aliases: --from-date, --start-time.",
        )
        parser.add_argument(
            "--until",
            "--to-date",
            "--end-time",
            type=str,
            default=None,
            dest="until",
            help="Only include files up to this date (same formats as --since). "
            "Aliases: --to-date, --end-time.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = max(0, int(options["limit"] or 0))
        path_arg = options["path"]
        root = (
            Path(path_arg).expanduser().resolve()
            if path_arg
            else get_discussion_export_dir()
        )

        try:
            since_dt = parse_iso_datetime(options.get("since"))
            until_dt = parse_iso_datetime(options.get("until"))
        except ValueError as e:
            raise CommandError(str(e)) from e
        if since_dt and until_dt and since_dt > until_dt:
            raise CommandError("since must be on or before until")

        cfg_guild = (getattr(settings, "DISCORD_SERVER_ID", "") or "").strip()
        expected = options["guild_id"]
        if expected is None and cfg_guild:
            try:
                expected = int(cfg_guild)
            except ValueError:
                expected = None

        if not root.is_dir():
            raise CommandError(f"Not a directory: {root}")

        paths = list(iter_discussion_json_files(root))
        paths = [p for p in paths if json_path_in_date_window(p, since_dt, until_dt)]
        if limit:
            paths = paths[:limit]

        self.stdout.write(f"Found {len(paths)} JSON file(s) under {root}")
        if not paths:
            return

        if dry_run:
            for p in paths:
                self.stdout.write(f"  {p.relative_to(root)}")
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes"))
            return

        processed = 0
        for i, json_path in enumerate(paths, 1):
            try:
                data = parse_exported_json(json_path)
                channel_data = {
                    "guild": data.get("guild", {}),
                    "channel": data.get("channel", {}),
                    "messages": data.get("messages", []),
                }
                ch = channel_data["channel"].get("name", "?")
                n = len(channel_data["messages"])
                self.stdout.write(
                    f"  [{i}/{len(paths)}] {json_path.name} #{ch}: {n} msgs"
                )
                asyncio.run(
                    persist_exporter_channel_payloads(
                        [channel_data],
                        expected_guild_id=expected,
                    )
                )
                processed += 1
            except Exception as e:
                logger.exception("Backfill failed for %s: %s", json_path, e)
                self.stdout.write(self.style.WARNING(f"  Skip {json_path.name}: {e}"))

        self.stdout.write(
            self.style.SUCCESS(f"✓ Backfill finished ({processed} file(s))")
        )
