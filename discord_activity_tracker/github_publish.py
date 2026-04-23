"""Upload Discord markdown exports to a GitHub repo (API upload, no local git required)."""

from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings

from github_ops import get_github_token, upload_folder_to_github

logger = logging.getLogger(__name__)

DEFAULT_BRANCH = "main"


def discord_markdown_repo_config() -> tuple[str, str, str] | None:
    """Return (owner, repo, branch) for Markdown upload, or None if not configured."""
    owner = getattr(settings, "DISCORD_MARKDOWN_REPO_OWNER", "") or ""
    repo = getattr(settings, "DISCORD_MARKDOWN_REPO_NAME", "") or ""
    branch = (
        getattr(settings, "DISCORD_MARKDOWN_REPO_BRANCH", DEFAULT_BRANCH)
        or DEFAULT_BRANCH
    ).strip()
    owner = owner.strip()
    repo = repo.strip()
    if not owner or not repo:
        return None
    return owner, repo, branch


def push_discord_markdown_to_github(local_folder: Path) -> bool:
    """
    Upload all files under local_folder to DISCORD_MARKDOWN_REPO_*.
    Returns True on reported API success.
    """
    cfg = discord_markdown_repo_config()
    if not cfg:
        logger.error(
            "DISCORD_MARKDOWN_REPO_OWNER / DISCORD_MARKDOWN_REPO_NAME not set; "
            "skipping upload."
        )
        return False
    owner, repo, branch = cfg
    if not local_folder.is_dir():
        logger.error("Markdown folder is not a directory: %s", local_folder)
        return False

    logger.info(
        "Uploading Discord markdown from %s to %s/%s@%s",
        local_folder,
        owner,
        repo,
        branch,
    )
    token = get_github_token(use="write")
    result = upload_folder_to_github(
        local_folder=local_folder,
        owner=owner,
        repo=repo,
        commit_message="chore: update Discord archive markdown",
        branch=branch,
        token=token,
    )
    if result.get("success"):
        logger.info("Discord markdown upload complete")
        return True
    msg = result.get("message") or "Upload failed"
    logger.error("Discord markdown upload failed: %s", msg)
    return False
