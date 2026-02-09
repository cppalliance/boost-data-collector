"""Tests for boost_library_tracker models."""
import pytest
from boost_library_tracker.models import BoostLibraryRepository, BoostLibrary


@pytest.mark.django_db
def test_boost_library_repository_extends_github_repo(boost_library_repository, github_repository):
    """BoostLibraryRepository uses same PK as parent GitHubRepository."""
    assert boost_library_repository.pk == github_repository.pk
    assert boost_library_repository.repo_name == github_repository.repo_name


@pytest.mark.django_db
def test_boost_library_belongs_to_repo(boost_library, boost_library_repository):
    """BoostLibrary is linked to BoostLibraryRepository."""
    assert boost_library.repo_id == boost_library_repository.pk
    assert boost_library in boost_library_repository.libraries.all()
    assert boost_library.name == "algorithm"


@pytest.mark.django_db
def test_multiple_libraries_in_repo(make_boost_library, boost_library_repository):
    """Multiple BoostLibraries can be created in the same repository."""
    a = make_boost_library(repo=boost_library_repository, name="algorithm")
    b = make_boost_library(repo=boost_library_repository, name="container")
    assert boost_library_repository.libraries.count() == 2
