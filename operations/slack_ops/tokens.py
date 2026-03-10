"""
Slack token resolution: get bot or app token from Django settings or env.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from operations.slack_ops.client import SlackAPIClient

logger = logging.getLogger(__name__)


def _slack_workspace_fallback() -> str:
    """Return default workspace key from SLACK_BOT_TOKEN: single key, or first key (order from SLACK_WORKSPACES)."""
    try:
        from django.conf import settings as django_settings

        tokens_map = getattr(django_settings, "SLACK_BOT_TOKEN", None)
    except Exception:
        tokens_map = None
    if not isinstance(tokens_map, dict) or not tokens_map:
        return ""
    return next(iter(tokens_map.keys()))


def get_default_workspace_key() -> str:
    """Return the default workspace key (single or first in SLACK_WORKSPACES). Empty if no workspaces configured."""
    return _slack_workspace_fallback()


def get_slack_bot_token(team_id: Optional[str] = None) -> str:
    """
    Return the Slack bot token for the given workspace (team_id).

    SLACK_BOT_TOKEN in settings is a dict (workspace_id -> token), built from env via
    SLACK_WORKSPACES and SLACK_BOT_TOKEN_<id>. When team_id is missing or empty,
    falls back to the default workspace key (single or first in SLACK_WORKSPACES).
    Logs error and raises ValueError only if both team_id and fallback are absent,
    or the token for that workspace is missing.
    """
    tid = (team_id or "").strip()
    if not tid:
        tid = _slack_workspace_fallback()
    if not tid:
        logger.error("workspace id is missing for Slack bot token lookup")
        raise ValueError("workspace id is required for get_slack_bot_token")

    try:
        from django.conf import settings

        tokens_map = getattr(settings, "SLACK_BOT_TOKEN", None)
    except Exception:
        tokens_map = None

    if not isinstance(tokens_map, dict) or tid not in tokens_map:
        logger.error(
            "workspace %s is missing from SLACK_BOT_TOKEN. Set SLACK_WORKSPACES and SLACK_BOT_TOKEN_%s in .env",
            tid,
            tid,
        )
        raise ValueError(
            f"workspace {tid!r} not found in SLACK_BOT_TOKEN. "
            f"Add {tid!r} to SLACK_WORKSPACES and set SLACK_BOT_TOKEN_{tid} in .env"
        )

    token = (tokens_map[tid] or "").strip()
    if not token:
        logger.error("token for workspace %s is missing in SLACK_BOT_TOKEN", tid)
        raise ValueError(f"token for workspace {tid!r} is missing in SLACK_BOT_TOKEN")

    return token


def get_slack_app_token() -> str:
    """
    Return SLACK_APP_TOKEN from Django settings or os.environ.
    Raises ValueError if not set.
    """
    try:
        from django.conf import settings

        token = getattr(settings, "SLACK_APP_TOKEN", None) or ""
    except Exception:
        token = ""
    if not token:
        token = os.environ.get("SLACK_APP_TOKEN", "")
    token = (token or "").strip()
    if not token:
        raise ValueError(
            "SLACK_APP_TOKEN is not set. Set it in Django settings or SLACK_APP_TOKEN env."
        )
    return token


def get_slack_client(
    bot_token: Optional[str] = None, team_id: Optional[str] = None
) -> "SlackAPIClient":
    """
    Get a SlackAPIClient with the given token, or the token for team_id from
    settings.SLACK_BOT_TOKEN (dict). When neither bot_token nor team_id is
    provided, get_slack_bot_token(team_id) uses the default workspace key (from SLACK_WORKSPACES) internally.
    """
    from operations.slack_ops.client import SlackAPIClient

    token = (bot_token or "").strip() or get_slack_bot_token(team_id)
    logger.debug("Creating Slack API client")
    return SlackAPIClient(token)
