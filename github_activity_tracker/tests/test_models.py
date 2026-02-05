"""Tests for github_activity_tracker models."""
import pytest
from github_activity_tracker.models import Language, GitHubRepository


@pytest.mark.django_db
def test_language_creation(language):
    """Language can be created with name."""
    assert language.name == "C++"
    assert language.id is not None


@pytest.mark.django_db
def test_github_repository_owner_relation(github_repository, github_account):
    """GitHubRepository is linked to owner GitHubAccount."""
    assert github_repository.owner_account_id == github_account.id
    assert github_repository in github_account.repositories.all()
