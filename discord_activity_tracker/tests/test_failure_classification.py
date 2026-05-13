"""Discord-related failure classification for CollectorFailureCategory."""

from __future__ import annotations

from core.errors import CollectorFailureCategory, classify_failure


def _make_discord_http_exception(status: int) -> Exception:
    cls = type("HTTPException", (Exception,), {})
    cls.__module__ = "discord.errors"
    exc = cls()
    exc.status = status
    return exc


def test_discord_http_429_is_rate_limit():
    exc = _make_discord_http_exception(429)
    assert classify_failure(exc) is CollectorFailureCategory.RATE_LIMIT


def test_discord_http_401_is_auth():
    exc = _make_discord_http_exception(401)
    assert classify_failure(exc) is CollectorFailureCategory.AUTH


def test_discord_http_403_is_auth():
    exc = _make_discord_http_exception(403)
    assert classify_failure(exc) is CollectorFailureCategory.AUTH


def test_discord_http_502_is_network():
    exc = _make_discord_http_exception(502)
    assert classify_failure(exc) is CollectorFailureCategory.NETWORK


def test_discord_http_404_is_unknown():
    exc = _make_discord_http_exception(404)
    assert classify_failure(exc) is CollectorFailureCategory.UNKNOWN


def test_discord_http_no_status_defaults_network():
    cls = type("HTTPException", (Exception,), {})
    cls.__module__ = "discord.errors"
    exc = cls()
    assert classify_failure(exc) is CollectorFailureCategory.NETWORK


def test_discord_login_failure_is_auth():
    cls = type("LoginFailure", (Exception,), {})
    cls.__module__ = "discord.errors"
    assert classify_failure(cls()) is CollectorFailureCategory.AUTH
