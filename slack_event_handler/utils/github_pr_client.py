"""
GitHub PR comment client for the Slack PR bot.
Reads GITHUB_TOKEN_WRITE and SLACK_PR_BOT_COMMENT_TEMPLATE from Django settings.
"""

import logging

from django.conf import settings
from github import Github

logger = logging.getLogger(__name__)

_gh: Github | None = None


def _get_client() -> Github:
    global _gh
    if _gh is None:
        token = (getattr(settings, "GITHUB_TOKEN_WRITE", "") or "").strip()
        if not token:
            raise ValueError(
                "Missing GITHUB_TOKEN_WRITE (or GITHUB_TOKEN) in Django settings / .env"
            )
        _gh = Github(token)
    return _gh


def post_pr_comment(owner: str, repo: str, pull_number: int) -> None:
    """
    Posts a comment to a GitHub PR using the configured template.
    Raises on network errors, 404 (not found), 403 (no access), etc.
    """
    template = (
        getattr(settings, "SLACK_PR_BOT_COMMENT_TEMPLATE", "")
        or "Automated comment from Slack bot."
    )
    gh = _get_client()
    repository = gh.get_repo(f"{owner}/{repo}")
    pull = repository.get_pull(pull_number)
    pull.create_issue_comment(template)
    logger.debug("Posted PR comment to %s/%s#%d", owner, repo, pull_number)
