"""
Workspace paths for wg21_paper_tracker.
Temporary file storage during download before uploading to GCS.
"""

import re
from pathlib import Path

from config.workspace import get_workspace_path

_APP_SLUG = "wg21_paper_tracker"
_RAW_APP_SLUG = f"raw/{_APP_SLUG}"
_MAILING_DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def get_workspace_root() -> Path:
    return get_workspace_path(_APP_SLUG)


def get_raw_dir(mailing_date: str) -> Path:
    """Return workspace/raw/wg21_paper_tracker/<mailing_date>/; creates if missing."""
    if not _MAILING_DATE_RE.fullmatch(mailing_date):
        raise ValueError("mailing_date must be in YYYY-MM format")
    raw_root = get_workspace_path(_RAW_APP_SLUG)
    path = raw_root / mailing_date
    path.mkdir(parents=True, exist_ok=True)
    return path
