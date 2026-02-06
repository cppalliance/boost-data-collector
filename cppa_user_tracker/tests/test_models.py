"""Tests for cppa_user_tracker models."""

import pytest
from cppa_user_tracker.models import (
    ProfileType,
)


@pytest.mark.django_db
def test_identity_creation(make_identity):
    """Identity can be created with display_name."""
    identity = make_identity(display_name="Dev User")
    assert identity.display_name == "Dev User"
    assert identity.id is not None


@pytest.mark.django_db
def test_github_account_sets_profile_type(github_account):
    """GitHubAccount.save() sets type to GITHUB."""
    assert github_account.type == ProfileType.GITHUB
    assert github_account.username == "testuser"


@pytest.mark.django_db
def test_github_account_identity_relation(github_account, identity):
    """GitHubAccount is linked to Identity."""
    assert github_account.identity_id == identity.id
    # identity.profiles returns BaseProfile instances; check by pk (GitHubAccount is subclass).
    assert identity.profiles.filter(pk=github_account.pk).exists()
