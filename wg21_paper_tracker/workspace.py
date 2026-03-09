"""
Workspace paths for wg21_paper_tracker.
Temporary file storage during download before uploading to GCS.
"""

from pathlib import Path

from config.workspace import get_workspace_path

_APP_SLUG = "wg21_paper_tracker"
_RAW_APP_SLUG = f"raw/{_APP_SLUG}"


def get_workspace_root() -> Path:
    return get_workspace_path(_APP_SLUG)


def get_raw_dir(mailing_date: str) -> Path:
    """Return workspace/raw/wg21_paper_tracker/<mailing_date>/; creates if missing."""
    raw_root = get_workspace_path(_RAW_APP_SLUG)
    path = raw_root / mailing_date
    path.mkdir(parents=True, exist_ok=True)
    return path
