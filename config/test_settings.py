"""
Test-only Django settings.
Imports base settings, then overrides for fast and isolated tests.
"""

import os
from pathlib import Path

from .settings import *  # noqa: F401, F403
from .settings import env

# Use SQLite in-memory for tests by default so no PostgreSQL is required.
# Set TEST_DATABASE_URL to run tests against PostgreSQL (e.g. in CI).
_test_db_url = os.environ.get("TEST_DATABASE_URL", "").strip()
if _test_db_url:
    DATABASES = {"default": env.db("TEST_DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}

BASE_DIR = Path(__file__).resolve().parent.parent
_test_dir = BASE_DIR / ".test_artifacts"
_test_dir.mkdir(exist_ok=True)
WORKSPACE_DIR = _test_dir / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)
for _slug in (
    "github_activity_tracker",
    "boost_library_tracker",
    "discord_activity_tracker",
    "shared",
):
    (WORKSPACE_DIR / _slug).mkdir(parents=True, exist_ok=True)
LOG_DIR = _test_dir / "logs"
LOG_DIR.mkdir(exist_ok=True)

GITHUB_TOKEN = ""
GITHUB_TOKENS_SCRAPING = []
GITHUB_TOKEN_WRITE = ""
