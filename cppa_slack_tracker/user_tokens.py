"""
Load Slack user OAuth tokens written by slack_oauth_server (credential file).

Same path as [slack_oauth_server](slack_oauth_server.py): optional SLACK_USER_TOKENS_PATH,
else BASE_DIR/credential/slack_user_tokens.json.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


def slack_user_tokens_path() -> Path:
    """Absolute path to slack_user_tokens.json."""
    override = (os.environ.get("SLACK_USER_TOKENS_PATH") or "").strip()
    if override:
        return Path(override)
    from django.conf import settings

    return Path(settings.BASE_DIR) / "credential" / "slack_user_tokens.json"


def load_slack_user_tokens() -> dict[str, dict]:
    """
    Return the raw JSON object: keys are ``team_id:user_id`` (or ``user_id``);
    values include user_id, team_id, access_token.
    """
    path = slack_user_tokens_path()
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load Slack user tokens from %s: %s", path, exc)
        return {}
    if not isinstance(data, dict):
        return {}
    return data  # type: ignore[return-value]


def iter_user_tokens_for_team(team_id: str) -> Iterator[tuple[str, str]]:
    """
    Yield (slack_user_id, access_token) for rows whose team_id matches ``team_id``.

    Skips malformed entries or empty tokens.
    """
    tid = (team_id or "").strip()
    if not tid:
        return
    for _key, row in load_slack_user_tokens().items():
        if not isinstance(row, dict):
            continue
        uid = (row.get("user_id") or "").strip()
        token = (row.get("access_token") or "").strip()
        row_team = (row.get("team_id") or "").strip()
        if not uid or not token:
            continue
        if row_team != tid:
            continue
        yield (uid, token)
