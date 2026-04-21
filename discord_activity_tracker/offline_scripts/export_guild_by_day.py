#!/usr/bin/env python3
"""
Export a Discord guild by day or by N-day chunks.
Uses DiscordChatExporter.Cli: lists channels, then for each channel exports
with --after / --before (local timezone, converted to UTC).
- Default: one JSON per channel per day. Output: EXPORT_ROOT/OUTPUT_BASE/CHANNEL/YYYY/YYYY-MM/YYYY-MM-DD.json
- EXPORT_CHUNK_DAYS=10: one JSON per 10 days. Output: EXPORT_ROOT/OUTPUT_BASE/CHANNEL/YYYY-MM-DD_to_YYYY-MM-DD.json
- Multiple tokens: TOKENS=token1,token2,token3 (round-robin per channel).
- Resume: skips channel-days/chunks that already exist under INPUT_BASE or OUTPUT_BASE.
- REFRESH_LAST_DATE=1: re-export only the last day/chunk per channel.
- FETCH_FROM_LAST=1: per channel, find last date in INPUT_BASE, then fetch from that date (incl.) to today.
- EXPORT_ROOT: defaults to <project_root>/cpp_discord_output (sibling of script/; same folder as run_export.py). INPUT_BASE / OUTPUT_BASE are subfolder names inside it (default read / output), or absolute paths. Relative EXPORT_ROOT is resolved under project root (not cwd). Existing JSON is detected under read/, output/, and directly under EXPORT_ROOT (legacy layout).
Runs up to PARALLEL channels at a time; within each channel, exports are sequential.
"""

import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None
    try:
        import pytz
    except ImportError:
        pytz = None

# ---------- Config (override with env vars) ----------
# Single token (legacy) or set TOKENS in env as comma-separated: TOKENS=token1,token2,token3
# Script default: one string or a list of token strings.
_TOKEN_DEFAULT = [
    "",
]
if os.environ.get("TOKENS", "").strip():
    TOKENS = [t.strip() for t in os.environ["TOKENS"].split(",") if t.strip()]
else:
    single = os.environ.get("TOKEN", "").strip()
    if single:
        TOKENS = [single]
    elif isinstance(_TOKEN_DEFAULT, list):
        TOKENS = [
            t for t in _TOKEN_DEFAULT if isinstance(t, str) and t.strip()
        ]
    else:
        TOKENS = (
            [str(_TOKEN_DEFAULT).strip()]
            if str(_TOKEN_DEFAULT).strip()
            else []
        )
GUILD_ID = os.environ.get("GUILD_ID", "331718482485837825")
START_DATE = os.environ.get("START_DATE", "2017-06-01")
END_DATE = os.environ.get("END_DATE", "").strip()  # default: today
PARALLEL = int(os.environ.get("PARALLEL", "1"))
CLI = os.environ.get("CLI", "DiscordChatExporter.Cli.exe")
TIMEZONE = os.environ.get("TIMEZONE", "America/New_York")
# If True (or env FAIL_ON_CHANNEL_ERROR=1), exit with code 1 when any channel fails (e.g. forbidden). Default: False.
FAIL_ON_CHANNEL_ERROR = (
    os.environ.get("FAIL_ON_CHANNEL_ERROR", "0").strip() == "1"
)
# If True (env REFRESH_LAST_DATE=1), re-export only the last date per channel (overwrite that day's file).
REFRESH_LAST_DATE = os.environ.get("REFRESH_LAST_DATE", "0").strip() == "1"
# If True (env FETCH_FROM_LAST=1), for each channel: find last date in INPUT_BASE, then fetch from that date (incl.) to today. Default: 0.
FETCH_FROM_LAST = os.environ.get("FETCH_FROM_LAST", "1").strip() == "1"
# Export in N-day chunks; file name is FROM_to_TO.json (e.g. 2017-06-01_to_2017-06-10). Use 1 for per-day (legacy).
EXPORT_CHUNK_DAYS = int(os.environ.get("EXPORT_CHUNK_DAYS", "1"))
# ----------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
# Data root next to script/: <project>/cpp_discord_output/ (sibling of script/)
_export_root_env = os.environ.get("EXPORT_ROOT", "").strip()
if _export_root_env:
    _er = Path(_export_root_env).expanduser()
    EXPORT_ROOT = (
        _er.resolve() if _er.is_absolute() else (PROJECT_ROOT / _er).resolve()
    )
else:
    EXPORT_ROOT = (PROJECT_ROOT / "cpp_discord_output").resolve()
# Subfolders inside EXPORT_ROOT (defaults: read = resume source, output = new JSON)
_DEFAULT_INPUT_SUBDIR = "read"
_DEFAULT_OUTPUT_SUBDIR = "output"
OUTPUT_BASE = os.environ.get("OUTPUT_BASE", _DEFAULT_OUTPUT_SUBDIR)
INPUT_BASE = os.environ.get("INPUT_BASE", _DEFAULT_INPUT_SUBDIR)

_CHANNEL_DEFAULT = [
    "Discussion - c-cpp-discussion",
]
if os.environ.get("CHANNEL_TO_EXPORT", "").strip():
    CHANNEL_TO_EXPORT = [
        x.strip()
        for x in os.environ["CHANNEL_TO_EXPORT"].split(",")
        if x.strip()
    ]
else:
    CHANNEL_TO_EXPORT = _CHANNEL_DEFAULT


def resolve_cli():
    """CLI path: if relative, resolve against SCRIPT_DIR (for Windows)."""
    p = Path(CLI)
    if not p.is_absolute():
        p = SCRIPT_DIR / p
    return str(p)


def _export_data_dir(base_key: str) -> Path:
    """Read/write root: absolute path if base_key is absolute, else EXPORT_ROOT / base_key."""
    p = Path(base_key)
    if p.is_absolute():
        return p.resolve()
    return (EXPORT_ROOT / p).resolve()


# Characters to sanitize for path: \ / : * ? " < > |
SANITIZE_RE = re.compile(r'[\\/:*?"<>|]')


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from CLI output."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def sanitize_name(name: str) -> str:
    """Sanitize channel name for use in filesystem paths."""
    return SANITIZE_RE.sub("-", name).strip()


def channel_name_for_path(full: str) -> str:
    """Strip guild (first segment): 'Guild - Category - Channel' -> 'Category - Channel'."""
    if " - " in full:
        return full.split(" - ", 1)[1].strip()
    return full.strip()


def get_timezone():
    """Return timezone object for TIMEZONE (zoneinfo or pytz)."""
    if ZoneInfo is not None:
        return ZoneInfo(TIMEZONE), ZoneInfo("UTC")
    if pytz is not None:
        return pytz.timezone(TIMEZONE), pytz.UTC
    raise RuntimeError(
        "Need zoneinfo (Python 3.9+) or pytz for timezone support"
    )


def date_to_utc_range(date_str: str):
    """Convert calendar day (local TZ) to (after_utc, before_utc) as 'YYYY-MM-DD HH:MM:SS'."""
    tz_local, utc = get_timezone()
    start_local = datetime.strptime(date_str, "%Y-%m-%d")
    if ZoneInfo is not None:
        start_local = start_local.replace(tzinfo=tz_local)
    else:
        start_local = tz_local.localize(start_local)
    end_local = start_local + timedelta(days=1)
    after_utc = start_local.astimezone(utc).strftime("%Y-%m-%d %H:%M:%S")
    before_utc = end_local.astimezone(utc).strftime("%Y-%m-%d %H:%M:%S")
    return after_utc, before_utc


def date_range_to_utc_range(start_date_str: str, end_date_str: str):
    """Convert date range (inclusive) to (after_utc, before_utc). before_utc is start of day after end_date."""
    tz_local, utc = get_timezone()
    start_local = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_local = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)
    if ZoneInfo is not None:
        start_local = start_local.replace(tzinfo=tz_local)
        end_local = end_local.replace(tzinfo=tz_local)
    else:
        start_local = tz_local.localize(start_local)
        end_local = tz_local.localize(end_local)
    after_utc = start_local.astimezone(utc).strftime("%Y-%m-%d %H:%M:%S")
    before_utc = end_local.astimezone(utc).strftime("%Y-%m-%d %H:%M:%S")
    return after_utc, before_utc


def get_chunks_from_dates(
    dates_list: list[str], chunk_days: int
) -> list[Tuple[str, str]]:
    """Split a list of YYYY-MM-DD dates into chunks of up to chunk_days. Returns [(start, end), ...]."""
    if chunk_days <= 1 or not dates_list:
        return [(d, d) for d in dates_list]
    chunks = []
    i = 0
    while i < len(dates_list):
        start = dates_list[i]
        j = min(i + chunk_days, len(dates_list)) - 1
        end = dates_list[j]
        chunks.append((start, end))
        i = j + 1
    return chunks


def _unique_export_bases() -> tuple[str, ...]:
    """Folders to scan for existing exports (resume / FETCH_FROM_LAST). Dedup if INPUT_BASE == OUTPUT_BASE."""
    if INPUT_BASE == OUTPUT_BASE:
        return (INPUT_BASE,)
    return (INPUT_BASE, OUTPUT_BASE)


def _iter_scan_roots() -> tuple[Path, ...]:
    """Roots searched for already-exported JSON (resume, skip-if-exists, last-date).

    Includes INPUT_BASE and OUTPUT_BASE under EXPORT_ROOT, plus EXPORT_ROOT itself
    so legacy trees (channel/... directly under cpp_discord_output) are visible.
    Deduped by resolved path.
    """
    seen: set[Path] = set()
    roots: list[Path] = []
    for base in _unique_export_bases():
        p = _export_data_dir(base)
        r = p.resolve()
        if r not in seen:
            seen.add(r)
            roots.append(p)
    er = EXPORT_ROOT.resolve()
    if er not in seen:
        roots.append(EXPORT_ROOT)
    return tuple(roots)


def output_file_exists(sanitized_name: str, date_str: str) -> bool:
    """True if the JSON for this channel/day already exists (resume)."""
    year = date_str[:4]
    month = date_str[5:7]
    rel = Path(sanitized_name) / year / f"{year}-{month}" / f"{date_str}.json"
    for root in _iter_scan_roots():
        if (root / rel).is_file():
            return True
    return False


def chunk_file_path(
    sanitized_name: str,
    start_date: str,
    end_date: str,
    *,
    base: Optional[str] = None,
) -> Path:
    """Path for a 10-day chunk file: base/CHANNEL/YYYY-MM-DD_to_YYYY-MM-DD.json. Default base=OUTPUT_BASE."""
    if base is None:
        base = OUTPUT_BASE
    return (
        _export_data_dir(base)
        / sanitized_name
        / f"{start_date}_to_{end_date}.json"
    )


def chunk_file_exists(
    sanitized_name: str, start_date: str, end_date: str
) -> bool:
    """True if the chunk file exists under any scanned export root."""
    name = f"{start_date}_to_{end_date}.json"
    rel = Path(sanitized_name) / name
    for root in _iter_scan_roots():
        if (root / rel).is_file():
            return True
    return False


def get_missing_dates(sanitized_name: str, dates_list: list[str]) -> list[str]:
    """Return only dates that are not yet exported (for resume)."""
    return [d for d in dates_list if not output_file_exists(sanitized_name, d)]


def get_missing_chunks(
    sanitized_name: str, chunks: list[Tuple[str, str]]
) -> list[Tuple[str, str]]:
    """Return only chunks that are not yet exported (resume for chunk mode)."""
    return [
        (s, e)
        for s, e in chunks
        if not chunk_file_exists(sanitized_name, s, e)
    ]


def get_last_export_date(sanitized_name: str) -> Optional[str]:
    """Return the latest (end) date that has a JSON file in this channel, or None.
    Supports both per-day files (YYYY-MM-DD.json) and chunk files (YYYY-MM-DD_to_YYYY-MM-DD.json).
    Scans read/, output/, and legacy paths directly under EXPORT_ROOT.
    """
    dates = []
    for root in _iter_scan_roots():
        channel_dir = root / sanitized_name
        if not channel_dir.is_dir():
            continue
        for f in channel_dir.rglob("*.json"):
            if not f.is_file():
                continue
            stem = f.stem
            if len(stem) == 10 and stem[4] == "-" and stem[7] == "-":
                dates.append(stem)
            elif "_to_" in stem:
                parts = stem.split("_to_", 1)
                if len(parts) == 2 and len(parts[1]) == 10:
                    dates.append(parts[1])
    return max(dates) if dates else None


def get_last_export_chunk(
    sanitized_name: str,
) -> Optional[Tuple[str, str]]:
    """Return (start_date, end_date) of the latest chunk file in this channel, or None.
    Only used when EXPORT_CHUNK_DAYS > 1 (chunk mode). Scans read/, output/, and EXPORT_ROOT.
    """
    best = None
    best_end = None
    for root in _iter_scan_roots():
        channel_dir = root / sanitized_name
        if not channel_dir.is_dir():
            continue
        for f in channel_dir.glob("*_to_*.json"):
            if not f.is_file():
                continue
            stem = f.stem
            if "_to_" not in stem:
                continue
            parts = stem.split("_to_", 1)
            if len(parts) != 2 or len(parts[0]) != 10 or len(parts[1]) != 10:
                continue
            if (
                parts[0][4] == "-"
                and parts[0][7] == "-"
                and parts[1][4] == "-"
                and parts[1][7] == "-"
            ):
                if best_end is None or parts[1] > best_end:
                    best = (parts[0], parts[1])
                    best_end = parts[1]
    return best


def fetch_channels(token: str):
    """Run CLI channels and parse (channel_id, sanitized_name) list. Skip threads."""
    exe = resolve_cli()
    cmd = [exe, "channels", "--token", token, "--guild", GUILD_ID]
    result = subprocess.run(
        cmd,
        cwd=SCRIPT_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )
    raw = (result.stdout or "") + (result.stderr or "")
    raw = strip_ansi(raw)
    if not raw.strip():
        raise SystemExit(
            "Could not get channel list. Check token, guild ID, and network."
        )

    channels = []
    for line in raw.splitlines():
        line = strip_ansi(line).strip()
        if not line or " * " in line:  # skip thread lines
            continue
        if " | " not in line:
            continue
        left, name = line.split(" | ", 1)
        cid = left.strip().replace(" ", "")
        if not cid.isdigit():
            continue
        name = name.split(" Thread ")[0].split(" | ")[0].strip()
        path_name = sanitize_name(channel_name_for_path(name))
        if not path_name or path_name == "-":
            path_name = cid
        if path_name not in CHANNEL_TO_EXPORT:
            continue
        channels.append((cid, path_name))
    return channels


def export_one_chunk(
    channel_id: str,
    sanitized_name: str,
    start_date_str: str,
    end_date_str: str,
    token: str,
    overwrite: bool = False,
) -> bool:
    """Export one channel for a date range (e.g. 10 days). File: START_to_END.json.
    Returns True on success, False on failure.
    """
    out_file = chunk_file_path(sanitized_name, start_date_str, end_date_str)
    if out_file.exists() and not overwrite:
        print(
            f"Skip (exists): {sanitized_name} {start_date_str}_to_{end_date_str}",
            file=sys.stderr,
        )
        return True

    out_file.parent.mkdir(parents=True, exist_ok=True)
    after_utc, before_utc = date_range_to_utc_range(
        start_date_str, end_date_str
    )

    exe = resolve_cli()
    cmd = [
        exe,
        "export",
        "--token",
        token,
        "--channel",
        channel_id,
        "--output",
        str(out_file),
        "--format",
        "Json",
        "--include-threads",
        "None",
        "--markdown",
        "True",
        "--respect-rate-limits",
        "True",
        "--after",
        after_utc,
        "--before",
        before_utc,
    ]
    MAX_RETRIES = 3
    for i in range(MAX_RETRIES):
        try:
            proc = subprocess.run(
                cmd,
                cwd=SCRIPT_DIR,
                capture_output=True,
                text=True,
                timeout=600,
                stdin=subprocess.DEVNULL,
            )
            if proc.returncode != 0:
                print(
                    f"FAILED: {sanitized_name} {start_date_str}_to_{end_date_str} (channel {channel_id})",
                    file=sys.stderr,
                )
                if proc.stderr:
                    print(proc.stderr, file=sys.stderr)
                continue
            print(
                f"OK: {sanitized_name} {start_date_str}_to_{end_date_str}",
                file=sys.stderr,
            )
            return True
        except subprocess.TimeoutExpired:
            print(
                f"TIMEOUT: {sanitized_name} {start_date_str}_to_{end_date_str} (channel {channel_id})",
                file=sys.stderr,
            )
            if i < MAX_RETRIES - 1:
                print(f"Retrying... ({i + 1}/{MAX_RETRIES})", file=sys.stderr)
            else:
                print(
                    f"FAILED: {sanitized_name} {start_date_str}_to_{end_date_str} (channel {channel_id})",
                    file=sys.stderr,
                )
    return False


def export_one_day(
    channel_id: str,
    sanitized_name: str,
    date_str: str,
    token: str,
    overwrite: bool = False,
) -> bool:
    """Export one channel for one day. Returns True on success, False on failure.
    If overwrite=True, re-export even when the file exists (for refreshing last date).
    """
    year = date_str[:4]
    month = date_str[5:7]
    out_dir = (
        _export_data_dir(OUTPUT_BASE)
        / sanitized_name
        / year
        / f"{year}-{month}"
    )
    out_file = out_dir / f"{date_str}.json"

    if out_file.exists() and not overwrite:
        print(f"Skip (exists): {sanitized_name} {date_str}", file=sys.stderr)
        return True

    out_dir.mkdir(parents=True, exist_ok=True)
    after_utc, before_utc = date_to_utc_range(date_str)

    exe = resolve_cli()
    cmd = [
        exe,
        "export",
        "--token",
        token,
        "--channel",
        channel_id,
        "--output",
        str(out_file),
        "--format",
        "Json",
        "--include-threads",
        "None",
        "--markdown",
        "True",
        "--respect-rate-limits",
        "True",
        "--after",
        after_utc,
        "--before",
        before_utc,
    ]
    MAX_RETRIES = 3
    for i in range(MAX_RETRIES):
        try:
            proc = subprocess.run(
                cmd,
                cwd=SCRIPT_DIR,
                capture_output=True,
                text=True,
                timeout=300,
                stdin=subprocess.DEVNULL,
            )
            if proc.returncode != 0:
                print(
                    f"FAILED: {sanitized_name} {date_str} (channel {channel_id})",
                    file=sys.stderr,
                )
                if proc.stderr:
                    print(proc.stderr, file=sys.stderr)
                continue
            print(f"OK: {sanitized_name} {date_str}", file=sys.stderr)
            return True
        except subprocess.TimeoutExpired:
            print(
                f"TIMEOUT: {sanitized_name} {date_str} (channel {channel_id})",
                file=sys.stderr,
            )
            if i < MAX_RETRIES - 1:
                print(f"Retrying... ({i + 1}/{MAX_RETRIES})", file=sys.stderr)
            else:
                print(
                    f"FAILED: {sanitized_name} {date_str} (channel {channel_id})",
                    file=sys.stderr,
                )

    return False


def export_channel_days(args):
    """Export for one channel. args = (channel_id, sanitized_name, dates_or_chunks, token, overwrite=False).
    dates_or_chunks: list of date strings (per-day) or list of (start_date, end_date) tuples (chunk mode).
    """
    if len(args) == 5:
        channel_id, sanitized_name, dates_or_chunks, token, overwrite = args
    else:
        channel_id, sanitized_name, dates_or_chunks, token = args
        overwrite = False
    failed = False
    use_chunks = dates_or_chunks and isinstance(dates_or_chunks[0], tuple)
    if use_chunks:
        for start_d, end_d in dates_or_chunks:
            if not export_one_chunk(
                channel_id,
                sanitized_name,
                start_d,
                end_d,
                token,
                overwrite=overwrite,
            ):
                failed = True
                break
    else:
        for date_str in dates_or_chunks:
            if not export_one_day(
                channel_id,
                sanitized_name,
                date_str,
                token,
                overwrite=overwrite,
            ):
                failed = True
                break
    return (channel_id, sanitized_name, failed)


def main():
    if not TOKENS:
        print(
            "ERROR: Set TOKEN or TOKENS (env or edit script).", file=sys.stderr
        )
        sys.exit(1)

    print(
        f"EXPORT_ROOT={EXPORT_ROOT}\n"
        f"INPUT (read/resume)={_export_data_dir(INPUT_BASE)}\n"
        f"OUTPUT (write)={_export_data_dir(OUTPUT_BASE)}",
        file=sys.stderr,
    )

    end = END_DATE or datetime.now().strftime("%Y-%m-%d")
    start_dt = datetime.strptime(START_DATE, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    dates_list = []
    d = start_dt
    while d <= end_dt:
        dates_list.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    print("Fetching channel list...", file=sys.stderr)
    channels = fetch_channels(TOKENS[0])
    print(
        f"Found {len(channels)} channels. Using {len(TOKENS)} token(s).",
        file=sys.stderr,
    )

    chunk_mode = EXPORT_CHUNK_DAYS > 1
    if chunk_mode:
        chunks_list = get_chunks_from_dates(dates_list, EXPORT_CHUNK_DAYS)
        print(
            f"Chunk mode: {EXPORT_CHUNK_DAYS} days per file (from_date_to_date.json). {len(chunks_list)} chunk(s).",
            file=sys.stderr,
        )

    if REFRESH_LAST_DATE:
        # Re-fetch only the last date/chunk per channel (overwrite).
        work = []
        for i, (cid, cname) in enumerate(channels):
            if chunk_mode:
                last_chunk = get_last_export_chunk(cname)
                if not last_chunk:
                    continue
                token = TOKENS[i % len(TOKENS)]
                work.append((cid, cname, [last_chunk], token, True))
            else:
                last_date = get_last_export_date(cname)
                if not last_date:
                    continue
                token = TOKENS[i % len(TOKENS)]
                work.append((cid, cname, [last_date], token, True))
        print(
            f"REFRESH_LAST_DATE: re-exporting last {'chunk' if chunk_mode else 'day'} for {len(work)} channel(s).",
            file=sys.stderr,
        )
    elif FETCH_FROM_LAST:
        # 1) Channel list done. 2) Find last date per channel. 3) Fetch from that date (incl.) to today.
        today_str = datetime.now().strftime("%Y-%m-%d")
        work = []
        for i, (cid, cname) in enumerate(channels):
            last_date = get_last_export_date(cname)
            if last_date is None:
                last_date = START_DATE
            start_dt = datetime.strptime(last_date, "%Y-%m-%d")
            end_dt = datetime.strptime(today_str, "%Y-%m-%d")
            if start_dt > end_dt:
                continue
            dates_from_last = []
            d = start_dt
            while d <= end_dt:
                dates_from_last.append(d.strftime("%Y-%m-%d"))
                d += timedelta(days=1)
            if not dates_from_last:
                continue
            token = TOKENS[i % len(TOKENS)]
            if chunk_mode:
                chunks = get_chunks_from_dates(
                    dates_from_last, EXPORT_CHUNK_DAYS
                )
                work.append((cid, cname, chunks, token, True))
            else:
                work.append((cid, cname, dates_from_last, token, True))
        print(
            f"FETCH_FROM_LAST: fetching from last date (incl.) to today for {len(work)} channel(s).",
            file=sys.stderr,
        )
    else:
        print(
            f"Date range: {START_DATE} to {end} ({len(dates_list)} days). Running up to {PARALLEL} channels in parallel.",
            file=sys.stderr,
        )
        work = []
        for i, (cid, cname) in enumerate(channels):
            if chunk_mode:
                missing = get_missing_chunks(cname, chunks_list)
                if not missing:
                    continue
                token = TOKENS[i % len(TOKENS)]
                work.append((cid, cname, missing, token))
            else:
                missing = get_missing_dates(cname, dates_list)
                if not missing:
                    continue
                token = TOKENS[i % len(TOKENS)]
                work.append((cid, cname, missing, token))

    if chunk_mode:
        total_chunks = len(channels) * len(chunks_list)
    else:
        total_chunks = len(channels) * len(dates_list)
    already_done = total_chunks - sum(len(w[2]) for w in work)
    if already_done and not REFRESH_LAST_DATE and not FETCH_FROM_LAST:
        unit = "chunk(s)" if chunk_mode else "channel-day(s)"
        print(
            f"Resume: {already_done} {unit} already exported; {sum(len(w[2]) for w in work)} left.",
            file=sys.stderr,
        )
    if not work:
        print(
            "Nothing to do (all channel-days already exported).",
            file=sys.stderr,
        )
        return

    failed_channels = []
    if PARALLEL <= 1:
        for item in work:
            cid, cname = item[0], item[1]
            print(f"Channel {cid} ({cname})...", file=sys.stderr)
            _, __, failed = export_channel_days(item)
            if failed:
                failed_channels.append(cid)
    else:
        with ThreadPoolExecutor(max_workers=PARALLEL) as executor:
            futures = {
                executor.submit(export_channel_days, a): a for a in work
            }
            for future in as_completed(futures):
                cid, cname, failed = future.result()
                if failed:
                    failed_channels.append(cid)

    if failed_channels:
        print(
            f"Some channel(s) could not be exported (e.g. forbidden = no read permission). Channel IDs: {failed_channels}",
            file=sys.stderr,
        )
        if FAIL_ON_CHANNEL_ERROR:
            sys.exit(1)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
