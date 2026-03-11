"""
Management command: run_cppa_youtube_script_tracker

4-phase pipeline:
  Phase 1: Process existing metadata queue JSONs → persist to DB →
           move JSON to raw/metadata/ (permanent archive).
  Phase 2: Determine start_time, fetch video metadata from YouTube Data API v3,
           write to metadata queue (short-lived), persist to DB,
           move JSON to raw/metadata/ (permanent archive).
  Phase 3: Download VTT transcripts via yt-dlp for videos with has_transcript=False;
           save directly to raw/transcripts/ (never deleted).
  Phase 4: Pinecone upsert via run_cppa_pinecone_sync.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from typing import Optional

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from cppa_user_tracker.services import get_or_create_youtube_speaker
from cppa_youtube_script_tracker.fetcher import fetch_videos
from cppa_youtube_script_tracker.models import YouTubeVideo
from cppa_youtube_script_tracker.preprocessor import preprocess_youtube_for_pinecone
from cppa_youtube_script_tracker.services import (
    get_or_create_channel,
    get_or_create_tag,
    get_or_create_video,
    link_speaker_to_video,
    link_tag_to_video,
    update_video_transcript,
)
from cppa_youtube_script_tracker.transcript import download_vtt
from cppa_youtube_script_tracker.workspace import (
    get_metadata_queue_path,
    get_raw_metadata_path,
    get_raw_transcripts_dir,
    iter_metadata_queue_jsons,
)

logger = logging.getLogger(__name__)

PINECONE_NAMESPACE_ENV_KEY = "YOUTUBE_PINECONE_NAMESPACE"
_DEFAULT_PINECONE_NAMESPACE = "youtube-scripts"

YOUTUBE_COOKIES_FILE = os.getenv("YOUTUBE_COOKIES_FILE", "youtube_cookies.txt")


def _clean_text(value: object) -> str:
    """Return DB-safe text (PostgreSQL rejects NUL bytes)."""
    if value is None:
        return ""
    value = str(value).replace("\x00", "").replace("\u2019", "'")

    return value


def _extract_speakers_from_title(title: str) -> list[str]:
    """Heuristic: extract speaker names from talk titles like 'Topic - Speaker Name'.

    Returns a list of candidate names (may be empty if no pattern matched).
    """
    if not title:
        return []
    for sep in (" - ", " — ", " | "):
        if sep in title:
            candidate = title.split(sep)[-1].strip()
            if candidate and len(candidate) < 80 and " " in candidate:
                return [candidate]
    return []


def _move_to_raw(video_id: str, queue_path) -> None:
    """Move a metadata JSON from queue to raw/metadata/ (permanent archive)."""
    try:
        raw_path = get_raw_metadata_path(video_id)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(queue_path), str(raw_path))
    except Exception:
        logger.warning(
            "_move_to_raw: could not move %s to raw/metadata/, removing instead",
            queue_path,
        )
        try:
            queue_path.unlink(missing_ok=True)
        except Exception:
            pass


def _persist_video(video_data: dict) -> tuple[bool, bool]:
    """Persist one video metadata dict to DB. Returns (created, skipped)."""
    video_id = _clean_text(video_data.get("video_id", "")).strip()
    if not video_id:
        return False, True

    channel_id = _clean_text(video_data.get("channel_id", "")).strip()
    channel_title = _clean_text(video_data.get("channel_title", "")).strip()
    channel = get_or_create_channel(channel_id, channel_title) if channel_id else None

    metadata = {
        "title": _clean_text(video_data.get("title", "")),
        "description": _clean_text(video_data.get("description", "")),
        "published_at": video_data.get("published_at"),
        "duration_seconds": video_data.get("duration_seconds", 0),
        "view_count": video_data.get("view_count"),
        "like_count": video_data.get("like_count"),
        "comment_count": video_data.get("comment_count"),
        "search_term": _clean_text(video_data.get("search_term", "")),
        "scraped_at": video_data.get("scraped_at"),
    }

    try:
        video, created = get_or_create_video(
            video_id=video_id, channel=channel, metadata_dict=metadata
        )
    except Exception:
        logger.exception("_persist_video: failed to persist video_id=%s", video_id)
        return False, True

    if created:
        for name in _extract_speakers_from_title(
            _clean_text(video_data.get("title", ""))
        ):
            try:
                speaker, _ = get_or_create_youtube_speaker(display_name=name)
                link_speaker_to_video(video, speaker)
            except Exception:
                logger.warning(
                    "_persist_video: could not link speaker %r to video %s",
                    name,
                    video_id,
                )

        for raw_tag in video_data.get("tags") or []:
            tag_name = _clean_text(raw_tag).strip()
            if not tag_name:
                continue
            try:
                tag = get_or_create_tag(tag_name)
                link_tag_to_video(video, tag)
            except Exception:
                logger.warning(
                    "_persist_video: could not link tag %r to video %s",
                    tag_name,
                    video_id,
                )

    return created, False


def _process_queue() -> tuple[int, int]:
    """Phase 1: load each metadata queue JSON, persist to DB, move to raw/metadata/.

    Returns (files_processed, videos_skipped).
    """
    processed = 0
    skipped = 0
    for path in iter_metadata_queue_jsons():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else [data]
            persist_ok = True
            last_video_id = ""
            for item in items:
                try:
                    _, was_skipped = _persist_video(item)
                    last_video_id = item.get("video_id", "")
                    if was_skipped:
                        skipped += 1
                except Exception:
                    persist_ok = False
                    logger.exception(
                        "_process_queue: persist failed for video_id=%s in %s",
                        item.get("video_id", "?"),
                        path,
                    )
                    skipped += 1
            if persist_ok:
                _move_to_raw(last_video_id or path.stem, path)
            processed += 1
        except Exception:
            logger.exception("_process_queue: failed to read %s", path)
    return processed, skipped


def _get_start_time_from_db() -> Optional[datetime]:
    """Return the latest published_at from YouTubeVideo, or None if table is empty."""
    latest = YouTubeVideo.objects.order_by("-published_at").first()
    return latest.published_at if latest and latest.published_at else None


def _resolve_start_time(start_time_arg: str, dry_run: bool) -> datetime:
    """Resolve the start_time for Phase 2 fetch.

    Priority: CLI arg → latest DB record → YOUTUBE_DEFAULT_PUBLISHED_AFTER → 2015-01-01.
    """
    if start_time_arg:
        dt = parse_datetime(start_time_arg)
        if dt:
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    if not dry_run:
        db_dt = _get_start_time_from_db()
        if db_dt:
            logger.info(
                "run_cppa_youtube_script_tracker: using start_time from DB: %s", db_dt
            )
            return db_dt

    default_after = (
        getattr(settings, "YOUTUBE_DEFAULT_PUBLISHED_AFTER", None) or ""
    ).strip()
    if default_after:
        dt = parse_datetime(default_after)
        if dt:
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    fallback = datetime(2015, 1, 1, tzinfo=timezone.utc)
    logger.warning(
        "run_cppa_youtube_script_tracker: no start_time available; defaulting to %s",
        fallback,
    )
    return fallback


def _resolve_end_time(end_time_arg: str) -> datetime:
    """Parse end_time CLI arg or default to now()."""
    if end_time_arg:
        dt = parse_datetime(end_time_arg)
        if dt:
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    return datetime.now(tz=timezone.utc)


def _persist_fetched_video(vdata: dict) -> tuple[bool, bool]:
    """Write video to metadata queue/, persist to DB, move to raw/metadata/. Returns (created, skipped)."""
    vid = vdata.get("video_id", "")
    if not vid:
        return False, True

    queue_path = get_metadata_queue_path(vid)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(json.dumps(vdata, indent=2, default=str), encoding="utf-8")

    try:
        was_created, was_skipped = _persist_video(vdata)
        _move_to_raw(vid, queue_path)
        return was_created, was_skipped
    except Exception:
        logger.exception(
            "run_cppa_youtube_script_tracker: Phase 2 persist failed for video_id=%s",
            vid,
        )
        return False, True


def _run_phase_2(
    start_time: datetime,
    end_time: datetime,
    channel_title: str,
) -> tuple[int, int]:
    """Fetch new videos and persist them. Returns (created_count, skipped_count)."""
    existing_ids: set[str] = set(
        YouTubeVideo.objects.values_list("video_id", flat=True)
    )
    videos = fetch_videos(
        published_after=start_time,
        published_before=end_time,
        channel_title=channel_title or None,
        skip_video_ids=existing_ids,
    )
    created_count = 0
    skipped_count = 0
    for vdata in videos:
        was_created, was_skipped = _persist_fetched_video(vdata)
        if was_created:
            created_count += 1
        elif was_skipped:
            skipped_count += 1
    return created_count, skipped_count


def _run_phase_3() -> tuple[int, int]:
    """Download VTT transcripts for videos that don't have one yet.

    Saves directly to raw/transcripts/ (never deleted).
    Returns (ok_count, fail_count).
    """
    pending = list(
        YouTubeVideo.objects.filter(has_transcript=False).values_list(
            "video_id", flat=True
        )
    )
    transcripts_dir = get_raw_transcripts_dir()
    ok = 0
    fail = 0
    for vid in pending:
        try:
            vtt_path = download_vtt(
                vid, output_dir=transcripts_dir, cookies_file=YOUTUBE_COOKIES_FILE
            )
            if vtt_path:
                video_obj = YouTubeVideo.objects.get(video_id=vid)
                update_video_transcript(video_obj, str(vtt_path))
                ok += 1
            else:
                fail += 1
        except Exception:
            fail += 1
            logger.exception(
                "run_cppa_youtube_script_tracker: transcript download failed for %s",
                vid,
            )
    return ok, fail


def _run_pinecone_sync(app_id: str, namespace: str) -> None:
    """Trigger run_cppa_pinecone_sync if app_id and namespace are set."""
    if not app_id:
        logger.warning("Pinecone sync skipped: --pinecone-app-id is empty.")
        return
    if not namespace:
        logger.warning(
            "Pinecone sync skipped: namespace is empty (set --pinecone-namespace or %s).",
            PINECONE_NAMESPACE_ENV_KEY,
        )
        return
    try:
        call_command(
            "run_cppa_pinecone_sync",
            app_id=app_id,
            namespace=namespace,
            preprocess_fn=preprocess_youtube_for_pinecone,
        )
        logger.info(
            "run_cppa_youtube_script_tracker: Pinecone sync complete (app_id=%s, namespace=%s)",
            app_id,
            namespace,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning(
            "Pinecone sync skipped/failed (run_cppa_pinecone_sync unavailable or errored): %s",
            exc,
        )


class Command(BaseCommand):
    help = (
        "Fetch YouTube C++ video metadata and transcripts, persist to DB, "
        "then optionally upsert to Pinecone. "
        "Processes existing metadata queue JSONs first, then fetches from the YouTube Data API."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--start-time",
            type=str,
            default="",
            help=(
                "ISO datetime string; fetch videos published after this time. "
                "Default: latest published_at in DB (after Phase 1), "
                "or YOUTUBE_DEFAULT_PUBLISHED_AFTER env var if DB is empty."
            ),
        )
        parser.add_argument(
            "--end-time",
            type=str,
            default="",
            help="ISO datetime string; fetch videos published before this time. Default: now().",
        )
        parser.add_argument(
            "--channel-title",
            type=str,
            default="",
            help=(
                "Restrict scraping to a specific channel title "
                "(must match a key in fetcher.C_PLUS_PLUS_CHANNELS or search by name)."
            ),
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Skip DB writes and API calls."
        )
        parser.add_argument(
            "--skip-transcript", action="store_true", help="Skip Phase 3."
        )
        parser.add_argument(
            "--pinecone-app-id",
            type=str,
            default="youtube",
            help="App ID passed to run_cppa_pinecone_sync.",
        )
        parser.add_argument(
            "--pinecone-namespace",
            type=str,
            default=os.getenv(PINECONE_NAMESPACE_ENV_KEY, _DEFAULT_PINECONE_NAMESPACE),
            help=f"Pinecone namespace. Default from env {PINECONE_NAMESPACE_ENV_KEY}.",
        )

    def handle(self, *args, **options):
        start_time_arg = (options.get("start_time") or "").strip()
        end_time_arg = (options.get("end_time") or "").strip()
        channel_title = (options.get("channel_title") or "").strip()
        dry_run: bool = options["dry_run"]
        skip_transcript: bool = options["skip_transcript"]
        pinecone_app_id = (options.get("pinecone_app_id") or "").strip()
        pinecone_namespace = (options.get("pinecone_namespace") or "").strip()

        logger.info(
            "run_cppa_youtube_script_tracker: starting "
            "(start_time=%s, end_time=%s, channel_title=%s, dry_run=%s, skip_transcript=%s)",
            start_time_arg or "auto",
            end_time_arg or "now",
            channel_title or "all",
            dry_run,
            skip_transcript,
        )

        try:
            self._phase_1(dry_run)
            start_time = _resolve_start_time(start_time_arg, dry_run)
            end_time = _resolve_end_time(end_time_arg)

            self.stdout.write(
                f"Phase 2: fetching videos {start_time.isoformat()} → {end_time.isoformat()} …"
            )

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Dry run: would fetch from {start_time.isoformat()} to "
                        f"{end_time.isoformat()}. No API calls or DB writes."
                    )
                )
                return

            self._phase_2(start_time, end_time, channel_title)
            self._phase_3(skip_transcript)
            _run_pinecone_sync(app_id=pinecone_app_id, namespace=pinecone_namespace)

        except Exception:
            logger.exception("run_cppa_youtube_script_tracker: unhandled error")
            raise

    def _phase_1(self, dry_run: bool) -> None:
        if dry_run:
            return
        files_processed, videos_skipped = _process_queue()
        self.stdout.write(
            f"Phase 1: processed {files_processed} queue file(s); {videos_skipped} video(s) skipped."
        )
        logger.info(
            "run_cppa_youtube_script_tracker: Phase 1 done; queue_files=%d, skipped=%d",
            files_processed,
            videos_skipped,
        )

    def _phase_2(
        self, start_time: datetime, end_time: datetime, channel_title: str
    ) -> None:
        created_count, skipped_count = _run_phase_2(start_time, end_time, channel_title)
        if created_count == 0 and skipped_count == 0:
            self.stdout.write(self.style.WARNING("Phase 2: no new videos fetched."))
            logger.info("run_cppa_youtube_script_tracker: Phase 2 — no new videos")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Phase 2 done: {created_count} created, {skipped_count} skipped."
                )
            )
            logger.info(
                "run_cppa_youtube_script_tracker: Phase 2 done; created=%d, skipped=%d",
                created_count,
                skipped_count,
            )

    def _phase_3(self, skip_transcript: bool) -> None:
        if skip_transcript:
            self.stdout.write("Phase 3: skipped (--skip-transcript).")
            return
        ok, fail = _run_phase_3()
        self.stdout.write(f"Phase 3 done: {ok} downloaded, {fail} unavailable.")
        logger.info(
            "run_cppa_youtube_script_tracker: Phase 3 done; ok=%d, fail=%d", ok, fail
        )
