"""
Fixtures for boost_library_tracker app.
Depends on github_activity_tracker (GitHubRepository) and cppa_user_tracker (GitHubAccount).
All model creation goes through the service API (see boost_library_tracker.services).
"""

import uuid

import pytest
from model_bakery import baker

from boost_library_tracker import services


def _make_boost_library_repository(*, owner_account=None, repo_name=None):
    """Create BoostLibraryRepository via service API (parent first, then get_or_create_boost_library_repo)."""
    if owner_account is None:
        owner_account = baker.make("cppa_user_tracker.GitHubAccount")
    if repo_name is None:
        repo_name = "repo-" + uuid.uuid4().hex[:8]
    parent = baker.make(
        "github_activity_tracker.GitHubRepository",
        owner_account=owner_account,
        repo_name=repo_name,
        stars=0,
        forks=0,
    )
    repo, _ = services.get_or_create_boost_library_repo(parent)
    return repo


@pytest.fixture
def boost_library_repository(db, github_repository):
    """BoostLibraryRepository (extends GitHubRepository) for tests. Uses service API."""
    repo, _ = services.get_or_create_boost_library_repo(github_repository)
    return repo


@pytest.fixture
def boost_library(db, boost_library_repository):
    """Single BoostLibrary in a BoostLibraryRepository. Uses service API."""
    lib, _ = services.get_or_create_boost_library(
        boost_library_repository, "algorithm"
    )
    return lib


@pytest.fixture
def make_boost_library():
    """Factory: create BoostLibrary via service API; repo created via service if not provided."""

    def _make(**kwargs):
        repo = kwargs.pop("repo", None)
        if repo is None:
            repo = _make_boost_library_repository(repo_name="boost-algorithm")
        name = kwargs.pop("name", None)
        if name is None:
            name = "lib-" + uuid.uuid4().hex[:6]
        lib, _ = services.get_or_create_boost_library(repo, name)
        return lib

    return _make
