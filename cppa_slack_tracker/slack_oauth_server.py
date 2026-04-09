"""
Slack user OAuth server

Loads `.env` from a fixed path beside this package; default token file is under
the same directory as that `.env` (see `_SLACK_OAUTH_DOTENV_PATH`).

- GET /                    → landing page with links (root is not Slack's callback)
- GET /slack/connect       → Slack authorize URL with CSRF `state` (server-side, TTL)
- GET /slack/oauth/callback → `?code=...&state=...`; state validated before token exchange
- GET /slack/authorized    → list authorized users (user_id, team_id; tokens not shown)
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import tempfile
import time
from html import escape
from pathlib import Path
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Route

# Default .env: cppa_slack_tracker/ -> project root .env
_SLACK_OAUTH_DOTENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_SLACK_OAUTH_DOTENV_PATH)
_DOTENV_DIR = _SLACK_OAUTH_DOTENV_PATH.parent

logger = logging.getLogger(__name__)


def _slack_user_tokens_file() -> Path:
    """Path to JSON map of OAuth user tokens; override with SLACK_USER_TOKENS_PATH."""
    override = (os.environ.get("SLACK_USER_TOKENS_PATH") or "").strip()
    if override:
        return Path(override)
    return _DOTENV_DIR / "credential" / "slack_user_tokens.json"


TOKENS_FILE = _slack_user_tokens_file()

# CSRF: one-time OAuth state values (server-side). Values are secrets.token_urlsafe;
# each maps to unix expiry time. Prevents replay after TTL via expiry + pop-on-use.
_oauth_states: dict[str, float] = {}


def _oauth_state_ttl_s() -> int:
    return max(60, int(os.environ.get("OAUTH_STATE_TTL_S", "600")))


def _purge_expired_oauth_states() -> None:
    now = time.time()
    expired = [s for s, until in _oauth_states.items() if until < now]
    for s in expired:
        del _oauth_states[s]


def _register_oauth_state(state: str) -> None:
    _purge_expired_oauth_states()
    _oauth_states[state] = time.time() + _oauth_state_ttl_s()


def _consume_oauth_state(state: str | None) -> bool:
    """Validate and consume a state (single use). False if missing, unknown, or expired."""
    if not state:
        return False
    _purge_expired_oauth_states()
    until = _oauth_states.pop(state, None)
    if until is None:
        return False
    if time.time() > until:
        return False
    return True


# ---------------------------------------------------------------------------
# Static HTML responses (predefined at import time)
# ---------------------------------------------------------------------------

_HTML_INDEX = HTMLResponse(
    content="""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>Boost data collector — Slack OAuth</title></head>
        <body>
        <h1>Slack OAuth helper</h1>
        <p>Use these links:</p>
        <ul>
          <li><a href="/slack/connect">Connect Slack</a> — start user authorization</li>
          <li><a href="/slack/authorized">Authorized users</a> — who has connected</li>
        </ul>
        <p>Slack redirects to <code>/slack/oauth/callback</code> after authorization.</p>
        </body>
        </html>
        """
)

_HTML_MISSING_CODE = HTMLResponse(
    content="""
            <!DOCTYPE html>
            <html><head><meta charset="utf-8"><title>Slack OAuth</title></head>
            <body>
              <h1>Missing code</h1>
              <p>No code in query string. Start from
                <a href="/slack/connect">/slack/connect</a>.
              </p>
            </body></html>
            """,
    status_code=400,
)

_HTML_SUCCESS = HTMLResponse(
    content="""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>Slack OAuth</title></head>
        <body>
        <h1>You're all set</h1>
        <p>This user is now authorized. Your app can receive
           "Subscribe to events on behalf of users" events for them.</p>
        <p>Token stored in <code>slack_user_tokens.json</code>.</p>
        </body>
        </html>
        """
)


# ---------------------------------------------------------------------------
# Dynamic HTML response builders (depend on runtime values)
# ---------------------------------------------------------------------------


def _html_auth_error(error: str) -> HTMLResponse:
    safe_error = escape(error)
    return HTMLResponse(
        content=f"""
            <!DOCTYPE html>
            <html><head><meta charset="utf-8"><title>Slack OAuth</title></head>
            <body><h1>Authorization failed</h1><p>Slack returned: {safe_error}</p></body></html>
            """,
        status_code=400,
    )


def _html_exchange_failed(error: str) -> HTMLResponse:
    safe_error = escape(error)
    return HTMLResponse(
        content=f"""
            <!DOCTYPE html>
            <html><head><meta charset="utf-8"><title>Slack OAuth</title></head>
            <body>
              <h1>Token exchange failed</h1>
              <p>{safe_error}</p>
            </body></html>
            """,
        status_code=400,
    )


def _html_invalid_oauth_state() -> HTMLResponse:
    return HTMLResponse(
        content="""
            <!DOCTYPE html>
            <html><head><meta charset="utf-8"><title>Slack OAuth</title></head>
            <body>
              <h1>Invalid or expired session</h1>
              <p>OAuth state was missing, invalid, or expired. Start again from
                <a href="/slack/connect">/slack/connect</a>.
              </p>
            </body></html>
            """,
        status_code=400,
    )


def _html_authorized(table_body: str) -> HTMLResponse:
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"><title>Authorized users</title></head>
        <body>
        <h1>Authorized users</h1>
        <p>Users who have completed the "Connect Slack" flow.
           Tokens are stored in <code>slack_user_tokens.json</code> (not shown here).</p>
        <table border="1">
        <thead><tr><th>User ID</th><th>Team ID</th></tr></thead>
        <tbody>
        {table_body}
        </tbody>
        </table>
        <p><a href="/slack/connect">Add another user</a></p>
        </body>
        </html>
        """
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_env(key: str) -> str:
    val = (os.environ.get(key) or "").strip()
    # If the value accidentally includes "KEY=" (e.g. pasted full .env line), strip the prefix.
    if val.startswith(f"{key}="):
        val = val.split("=", 1)[1].strip()
    if not val or val == "your_client_id_here" or val == "your_client_secret_here":
        raise RuntimeError(
            f"Set {key} in .env (copy from .env.example and fill in your Slack app credentials)"
        )
    return val


def _load_tokens() -> dict[str, dict]:  # type: ignore[type-arg]
    if not TOKENS_FILE.exists():
        return {}
    try:
        with TOKENS_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load Slack user tokens from %s: %s", TOKENS_FILE, exc)
        return {}
    if not isinstance(data, dict):
        return {}
    return data  # type: ignore[no-any-return]


def _ensure_tokens_dir() -> None:
    """Create credential dir with owner-only perms where possible."""
    # TODO: move token storage to a dedicated secret manager when available.
    TOKENS_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        TOKENS_FILE.parent.chmod(0o700)
    except OSError:
        # Best effort on non-POSIX filesystems/platforms.
        pass


def _save_tokens(data: dict[str, dict]) -> None:  # type: ignore[type-arg]
    _ensure_tokens_dir()
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=TOKENS_FILE.parent,
        delete=False,
        prefix=f"{TOKENS_FILE.name}.",
        suffix=".tmp",
    ) as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
        tmp_path = Path(f.name)
    try:
        tmp_path.chmod(0o600)
    except OSError:
        pass
    tmp_path.replace(TOKENS_FILE)
    try:
        TOKENS_FILE.chmod(0o600)
    except OSError:
        # Best effort on non-POSIX filesystems/platforms.
        pass


async def _exchange_code(code: str) -> dict:  # type: ignore[type-arg]
    """POST to oauth.v2.access.

    Returns Slack's JSON object on success. On transport, HTTP, or parse errors returns
    a dict with ok=False and an error string so slack_oauth_callback can call
    _html_exchange_failed.
    """
    try:
        client_id = _get_env("SLACK_CLIENT_ID")
        client_secret = _get_env("SLACK_CLIENT_SECRET")
        redirect_uri = _get_env("SLACK_REDIRECT_URI")
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://slack.com/api/oauth.v2.access",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        snippet = ""
        try:
            snippet = (exc.response.text or "")[:400]
        except Exception:
            logger.debug(
                "Failed to read HTTP error response body for Slack OAuth token exchange",
                exc_info=True,
            )
        err = f"HTTP {exc.response.status_code}"
        if snippet:
            err = f"{err}: {snippet}"
        return {"ok": False, "error": err}
    except httpx.RequestError as exc:
        return {"ok": False, "error": f"Token request failed: {exc}"}

    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "error": f"Invalid response from Slack (not JSON): {exc}"}

    if not isinstance(data, dict):
        return {
            "ok": False,
            "error": "Unexpected response from Slack (expected JSON object).",
        }
    return data


def _store_token(data: dict) -> None:  # type: ignore[type-arg]
    """Persist the authed_user token from an oauth.v2.access response."""
    authed_user = data.get("authed_user") or {}
    user_token = authed_user.get("access_token")
    user_id = authed_user.get("id")
    team_id = (data.get("team") or {}).get("id")
    if not (user_token and user_id):
        return
    tokens = _load_tokens()
    key = f"{team_id}:{user_id}" if team_id else user_id
    tokens[key] = {"user_id": user_id, "team_id": team_id, "access_token": user_token}
    _save_tokens(tokens)


async def index(_: Request) -> HTMLResponse:
    """Root URL — OAuth entry points live under /slack/…"""
    return _HTML_INDEX


async def slack_connect(_: Request) -> RedirectResponse:
    """Redirect user to Slack authorize URL (entry point for 'Connect Slack')."""
    client_id = _get_env("SLACK_CLIENT_ID")
    redirect_uri = _get_env("SLACK_REDIRECT_URI")
    user_scope = os.environ.get(
        "SLACK_USER_SCOPES",
        "channels:history,channels:read,groups:history,groups:read,"
        "im:history,im:read,mpim:history,mpim:read",
    )
    state = secrets.token_urlsafe(32)
    _register_oauth_state(state)
    params = {
        "client_id": client_id,
        "user_scope": user_scope,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    url = "https://slack.com/oauth/v2/authorize?" + urlencode(params)
    return RedirectResponse(url=url, status_code=302)


async def slack_oauth_callback(request: Request) -> HTMLResponse:
    """Handle redirect from Slack: exchange code for user token, store it, show success."""
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    state = request.query_params.get("state")

    if not _consume_oauth_state(state):
        return _html_invalid_oauth_state()

    if error:
        return _html_auth_error(error)

    if not code:
        return _HTML_MISSING_CODE

    try:
        data = await _exchange_code(code)
    except Exception as exc:
        return _html_exchange_failed(f"Token exchange failed: {exc}")

    if not data.get("ok"):
        return _html_exchange_failed(data.get("error", "Unknown error"))

    _store_token(data)

    return _HTML_SUCCESS


async def slack_authorized(_: Request) -> HTMLResponse:
    """List authorized users (user_id, team_id); tokens are not shown."""
    tokens = _load_tokens()
    rows = [
        f"<tr><td>{escape(str(d.get('user_id', '')))}</td>"
        f"<td>{escape(str(d.get('team_id', '')))}</td></tr>"
        for d in tokens.values()
    ]
    no_rows = '<tr><td colspan="2">No users authorized yet.</td></tr>'
    table_body = "\n".join(rows) if rows else no_rows
    return _html_authorized(table_body)


def _slack_oauth_debug_enabled() -> bool:
    """Starlette debug mode — off unless SLACK_OAUTH_DEBUG is truthy (unsafe for production)."""
    return os.environ.get("SLACK_OAUTH_DEBUG", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


app = Starlette(
    debug=_slack_oauth_debug_enabled(),
    routes=[
        Route("/", index),
        Route("/slack/connect", slack_connect),
        Route("/slack/oauth/callback", slack_oauth_callback),
        Route("/slack/authorized", slack_authorized),
    ],
)


def main() -> None:
    import uvicorn

    port = int(os.environ.get("SLACK_OAUTH_PORT", "8000"))
    host = (os.environ.get("HOST") or "127.0.0.1").strip() or "127.0.0.1"
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
