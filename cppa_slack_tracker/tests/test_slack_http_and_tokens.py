"""
Slack HTTP client and token resolution tests under cppa_slack_tracker (issue coverage).

Uses unittest.mock; exercises SlackAPIClient rate-limit/auth paths and token helpers.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.errors import CollectorFailureCategory, classify_failure
from core.operations.slack_ops.client import SlackAPIClient
from core.operations.slack_ops.tokens import (
    get_slack_app_token,
    get_slack_client,
)


def test_rate_limit_429_header_retries_then_succeeds():
    """HTTP 429 with Retry-After: client retries then returns JSON."""
    c = SlackAPIClient("xoxb-test")
    ok = MagicMock(
        status_code=200,
        json=lambda: {"ok": True, "channels": []},
        headers={},
        raise_for_status=MagicMock(),
    )
    rate_limited = MagicMock(
        status_code=429,
        headers={"Retry-After": "1"},
        json=lambda: {},
        raise_for_status=MagicMock(),
    )
    c.session.get = MagicMock(side_effect=[rate_limited, ok])
    with patch("core.operations.slack_ops.client.time.sleep") as sleep_mock:
        out = c.conversations_list()
    assert out == {"ok": True, "channels": []}
    sleep_mock.assert_called_once_with(1)


def test_rate_limit_body_error_rate_limited_retries():
    """Slack body error=rate_limited: client reads Retry-After header and retries."""
    c = SlackAPIClient("xoxb-test")
    first = MagicMock(
        status_code=200,
        json=lambda: {"ok": False, "error": "rate_limited"},
        headers={"Retry-After": "2"},
        raise_for_status=MagicMock(),
    )
    second = MagicMock(
        status_code=200,
        json=lambda: {"ok": True, "channels": [{"id": "C1"}]},
        headers={},
        raise_for_status=MagicMock(),
    )
    c.session.get = MagicMock(side_effect=[first, second])
    with patch("core.operations.slack_ops.client.time.sleep") as sleep_mock:
        out = c.conversations_list()
    assert out["ok"] is True
    assert out["channels"] == [{"id": "C1"}]
    sleep_mock.assert_called_once_with(2)


def test_auth_failure_invalid_auth_body():
    """Slack returns ok=False invalid_auth in JSON; client returns dict (no raise)."""
    c = SlackAPIClient("xoxb-bad")
    resp = MagicMock(
        status_code=200,
        json=lambda: {"ok": False, "error": "invalid_auth"},
        headers={},
        raise_for_status=MagicMock(),
    )
    c.session.get = MagicMock(return_value=resp)
    with patch("core.operations.slack_ops.client.time.sleep"):
        out = c.conversations_list()
    assert out == {"ok": False, "error": "invalid_auth"}


def test_auth_failure_http_401_classifies_as_auth():
    """CollectorFailureCategory: HTTP 401 maps to AUTH."""
    pytest.importorskip("requests")
    import requests

    exc = requests.HTTPError()
    resp = requests.Response()
    resp.status_code = 401
    exc.response = resp
    assert classify_failure(exc) is CollectorFailureCategory.AUTH


def test_get_slack_client_with_explicit_bot_token():
    client = get_slack_client(bot_token="xoxb-test")
    assert client.token == "xoxb-test"


def test_get_slack_client_for_team_id_resolves_from_settings(settings):
    settings.SLACK_BOT_TOKEN = {"T1": "xoxb-from-settings"}
    settings.SLACK_TEAM_ID = "T1"
    client = get_slack_client(team_id="T1")
    assert client.token == "xoxb-from-settings"


def test_get_slack_app_token_happy_path(settings):
    settings.SLACK_APP_TOKEN = {"T1": "xapp-ok"}
    settings.SLACK_TEAM_ID = "T1"
    assert get_slack_app_token("T1") == "xapp-ok"


def test_get_slack_app_token_missing_raises_value_error(settings):
    settings.SLACK_APP_TOKEN = {}
    settings.SLACK_TEAM_ID = "T1"
    with pytest.raises(ValueError, match="SLACK_APP_TOKEN"):
        get_slack_app_token("T1")
