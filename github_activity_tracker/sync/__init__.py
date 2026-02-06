"""
GitHub sync package: read last updated from DB, fetch from GitHub, save via services.

Split by entity: repos, commits, issues, pull_requests.
Entry point: sync_github(repo) runs all in order for that repo.
Accepts GitHubRepository or any subclass (e.g. BoostLibraryRepository); base fields are used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .commits import sync_commits
from .issues import sync_issues
from .pull_requests import sync_pull_requests
from .repos import sync_repos

if TYPE_CHECKING:
    from ..models import GitHubRepository


def sync_github(repo: GitHubRepository) -> None:
    """Run full sync for one repo: repos (metadata), then commits, issues, pull requests.

    Accepts GitHubRepository or a subclass (e.g. BoostLibraryRepository); the same
    base row is used, so extended models can be passed and sync will work.

    """
    sync_repos(repo)
    sync_commits(repo)
    sync_issues(repo)
    sync_pull_requests(repo)
