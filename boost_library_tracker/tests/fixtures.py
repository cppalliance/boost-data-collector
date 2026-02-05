"""
Fixtures for boost_library_tracker app.
Depends on github_activity_tracker (GitHubRepository) and cppa_user_tracker (GitHubAccount).
"""
import pytest
from model_bakery import baker


@pytest.fixture
def boost_library_repository(db, github_repository):
    """BoostLibraryRepository (extends GitHubRepository) for tests."""
    # BoostLibraryRepository is multi-table inheritance from GitHubRepository;
    # we need to create from boost_library_tracker model (it creates the parent too).
    return baker.make(
        "boost_library_tracker.BoostLibraryRepository",
        githubrepository_ptr=github_repository,
    )


@pytest.fixture
def boost_library(db, boost_library_repository):
    """Single BoostLibrary in a BoostLibraryRepository."""
    return baker.make(
        "boost_library_tracker.BoostLibrary",
        repo=boost_library_repository,
        name="algorithm",
    )


@pytest.fixture
def make_boost_library():
    """Factory: create BoostLibrary; repo created if not provided."""

    def _make(**kwargs):
        if "repo" not in kwargs:
            kwargs["repo"] = baker.make(
                "boost_library_tracker.BoostLibraryRepository",
                owner_account=baker.make("cppa_user_tracker.GitHubAccount"),
                repo_name="boost-algorithm",
            )
        if "name" not in kwargs:
            import uuid
            kwargs["name"] = "lib-" + uuid.uuid4().hex[:6]
        return baker.make("boost_library_tracker.BoostLibrary", **kwargs)

    return _make
