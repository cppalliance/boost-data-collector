"""
Workspace paths for wg21_paper_tracker.
Temporary file storage during download before uploading to GCS.
"""

import re
from pathlib import Path

from django.conf import settings

from config.workspace import get_workspace_path

_APP_SLUG = "wg21_paper_tracker"
_RAW_APP_SLUG = f"raw/{_APP_SLUG}"
_MAILING_DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def get_workspace_root() -> Path:
    return get_workspace_path(_APP_SLUG)


def get_raw_dir(mailing_date: str | None, year: int) -> Path:
    """Return workspace/raw/wg21_paper_tracker/<year>/<mailing_date>/; creates if missing."""
    if mailing_date is not None and not _MAILING_DATE_RE.fullmatch(mailing_date):
        raise ValueError("mailing_date must be in YYYY-MM format")
    if getattr(settings, "RAW_DIR", None):
        raw_root = Path(settings.RAW_DIR) / _APP_SLUG
    else:
        raw_root = get_workspace_path(_RAW_APP_SLUG)
    raw_root.mkdir(parents=True, exist_ok=True)
    if mailing_date:
        path = raw_root / str(year) / mailing_date
    else:
        path = raw_root / str(year)
    path.mkdir(parents=True, exist_ok=True)
    return path
