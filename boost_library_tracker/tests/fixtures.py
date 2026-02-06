"""
Fixtures for boost_library_tracker app.
Depends on github_activity_tracker (GitHubRepository) and cppa_user_tracker (GitHubAccount).
"""
from django.db import connection
from django.utils import timezone

import pytest
from model_bakery import baker

from boost_library_tracker.models import BoostLibraryRepository


@pytest.fixture
def boost_library_repository(db, github_repository):
    """BoostLibraryRepository (extends GitHubRepository) for tests."""
    # Insert only the child table row so the parent row is never updated (MTI create() would
    # UPDATE the parent with the child's empty attributes and violate owner_account_id NOT NULL).
    now = timezone.now()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO boost_library_tracker_boostlibraryrepository
                (githubrepository_ptr_id, created_at, updated_at)
            VALUES (%s, %s, %s)
            """,
            [github_repository.pk, now, now],
        )
    return BoostLibraryRepository.objects.get(pk=github_repository.pk)


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
