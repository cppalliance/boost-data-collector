"""
JSON file persistence for the PR bot job queue and rate-limit state.

State file layout:
  { "postedAt": [<unix_timestamp>, ...], "queue": [<job_dict>, ...] }

When team_id is provided, state is stored in state_<team_id>.json for multi-workspace support.
"""

import json
import os
import re
from copy import deepcopy
from typing import Any, Optional

_DEFAULT_STATE: dict[str, Any] = {"postedAt": [], "queue": []}


def _sanitize_team_id_for_path(team_id: str) -> str:
    """Safe filename segment from Slack team_id (e.g. T01234ABCD -> T01234ABCD)."""
    if not team_id:
        return "default"
    return re.sub(r"[^a-zA-Z0-9_-]", "_", team_id)


def _get_state_file_path(team_id: Optional[str] = None) -> str:
    """Resolve the state file path. If team_id is None, state.json; else state_<team_id>.json."""
    from slack_event_handler.workspace import get_data_dir

    data_dir = get_data_dir()
    if team_id:
        safe = _sanitize_team_id_for_path(team_id)
        return str(data_dir / f"state_{safe}.json")
    return str(data_dir / "state.json")


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)


def load_state(team_id: Optional[str] = None) -> dict[str, Any]:
    """Load state for the given team. team_id=None uses state.json (single-workspace)."""
    path = _get_state_file_path(team_id)
    try:
        _ensure_dir(path)
        if not os.path.exists(path):
            return deepcopy(_DEFAULT_STATE)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return deepcopy(_DEFAULT_STATE)


def save_state(state: dict[str, Any], team_id: Optional[str] = None) -> None:
    """Save state for the given team. team_id=None uses state.json (single-workspace)."""
    path = _get_state_file_path(team_id)
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
