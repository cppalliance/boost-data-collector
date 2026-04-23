"""Run bundled export_guild_by_day.py (per-day DiscordChatExporter) with Django settings."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import discord_activity_tracker
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from discord_activity_tracker.sync.dce_cli import (
    DiscordChatExporterCliNotFoundError,
    ensure_discord_chat_exporter_cli,
)
from discord_activity_tracker.workspace import get_workspace_root

logger = logging.getLogger(__name__)


def resolve_export_script() -> Path:
    """Path to export_guild_by_day.py (bundled or DISCORD_EXPORT_SCRIPT_DIR)."""
    custom = (getattr(settings, "DISCORD_EXPORT_SCRIPT_DIR", "") or "").strip()
    if custom:
        p = Path(custom).expanduser().resolve() / "export_guild_by_day.py"
        if p.is_file():
            return p
        raise CommandError(
            f"DISCORD_EXPORT_SCRIPT_DIR is set but script not found: {p}"
        )
    p = (
        Path(discord_activity_tracker.__file__).resolve().parent
        / "offline_scripts"
        / "export_guild_by_day.py"
    )
    if not p.is_file():
        raise CommandError(f"Bundled export script missing: {p}")
    return p


class Command(BaseCommand):
    help = (
        "Run export_guild_by_day.py (DiscordChatExporter per channel/day) using "
        "DISCORD_USER_TOKEN, DISCORD_SERVER_ID, and workspace paths. "
        "The CLI is resolved via ensure_discord_chat_exporter_cli() (pinned release zip on Windows, "
        "or git clone + dotnet publish on macOS/Linux when tools/ is empty). "
        "Import JSON into the DB with: python manage.py backfill_discord_json."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print resolved script, CLI, and env; do not execute the Python exporter.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        token = (getattr(settings, "DISCORD_USER_TOKEN", "") or "").strip()
        guild_id = (getattr(settings, "DISCORD_SERVER_ID", "") or "").strip()
        if not token:
            raise CommandError("DISCORD_USER_TOKEN is not set")
        if not guild_id:
            raise CommandError("DISCORD_SERVER_ID is not set")

        script_path = resolve_export_script()
        workspace_root = get_workspace_root()
        try:
            cli_path = ensure_discord_chat_exporter_cli()
        except DiscordChatExporterCliNotFoundError as e:
            raise CommandError(str(e)) from e

        env = os.environ.copy()
        env["TOKEN"] = token
        env["GUILD_ID"] = str(guild_id)
        env["EXPORT_ROOT"] = str(workspace_root)
        env["CLI"] = str(cli_path)
        env["CHANNEL_TO_EXPORT"] = getattr(
            settings, "DISCORD_CHANNEL_EXPORT_NAMES", "Discussion - c-cpp-discussion"
        )
        env["TIMEZONE"] = getattr(
            settings, "DISCORD_EXPORT_TIMEZONE", "America/New_York"
        )
        env["EXPORT_CHUNK_DAYS"] = str(
            int(getattr(settings, "DISCORD_EXPORT_CHUNK_DAYS", 1) or 1)
        )

        self.stdout.write(f"Script: {script_path}")
        self.stdout.write(f"CLI: {cli_path}")
        self.stdout.write(f"EXPORT_ROOT: {workspace_root}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — not invoking exporter"))
            return

        cwd = script_path.parent
        cmd = [sys.executable, str(script_path)]
        logger.info("Running %s with cwd=%s", cmd, cwd)
        proc = subprocess.run(cmd, cwd=cwd, env=env, check=False)
        if proc.returncode != 0:
            raise CommandError(
                f"export_guild_by_day.py exited with code {proc.returncode}"
            )
        self.stdout.write(self.style.SUCCESS("export_guild_by_day.py finished"))
