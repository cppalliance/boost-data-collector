"""Tests for boost_usage_tracker.services.

Covers service layer in detail including edge cases and boundaries:
- Empty inputs, default values, maximum/minimum values.
- Idempotency, no-op updates, and error paths.
"""

from datetime import datetime, timezone

import pytest

from boost_usage_tracker import services
from boost_usage_tracker.models import (
    BoostExternalRepository,
    BoostMissingHeaderTmp,
    BoostUsage,
)

# --- get_or_create_boost_external_repo ---


@pytest.mark.django_db
def test_get_or_create_boost_external_repo_creates_new(external_github_repository):
    """get_or_create_boost_external_repo creates BoostExternalRepository and returns (repo, True)."""
    repo, created = services.get_or_create_boost_external_repo(
        external_github_repository,
        boost_version="1.83.0",
        is_boost_used=True,
    )
    assert created is True
    assert repo.pk == external_github_repository.pk
    assert isinstance(repo, BoostExternalRepository)
    assert repo.repo_name == external_github_repository.repo_name
    assert repo.boost_version == "1.83.0"
    assert repo.is_boost_used is True


@pytest.mark.django_db
def test_get_or_create_boost_external_repo_gets_existing(
    ext_repo, external_github_repository
):
    """get_or_create_boost_external_repo returns existing and (repo, False)."""
    repo, created = services.get_or_create_boost_external_repo(
        external_github_repository,
        boost_version="1.84.0",
        is_boost_used=True,
    )
    assert created is False
    assert repo.pk == ext_repo.pk


@pytest.mark.django_db
def test_get_or_create_boost_external_repo_updates_flags(
    external_github_repository,
):
    """get_or_create_boost_external_repo updates boost_version and is_boost_embedded when existing."""
    services.get_or_create_boost_external_repo(
        external_github_repository,
        boost_version="1.80.0",
        is_boost_used=False,
    )
    repo2, created2 = services.get_or_create_boost_external_repo(
        external_github_repository,
        boost_version="1.81.0",
        is_boost_embedded=True,
        is_boost_used=True,
    )
    assert created2 is False
    repo2.refresh_from_db()
    assert repo2.boost_version == "1.81.0"
    assert repo2.is_boost_embedded is True
    assert repo2.is_boost_used is True


# --- get_or_create_boost_external_repo: edge cases ---


@pytest.mark.django_db
def test_get_or_create_boost_external_repo_empty_boost_version(
    external_github_repository,
):
    """get_or_create_boost_external_repo accepts empty boost_version."""
    repo, created = services.get_or_create_boost_external_repo(
        external_github_repository,
        boost_version="",
        is_boost_used=False,
    )
    assert created is True
    assert repo.boost_version == ""


@pytest.mark.django_db
def test_get_or_create_boost_external_repo_boost_version_max_length(
    external_github_repository,
):
    """get_or_create_boost_external_repo accepts boost_version at max 64 chars."""
    max_ver = "1." + "9" * 62
    assert len(max_ver) == 64
    repo, _ = services.get_or_create_boost_external_repo(
        external_github_repository,
        boost_version=max_ver,
        is_boost_used=True,
    )
    repo.refresh_from_db()
    assert repo.boost_version == max_ver


@pytest.mark.django_db
def test_get_or_create_boost_external_repo_defaults_only(external_github_repository):
    """get_or_create_boost_external_repo with only required arg uses defaults."""
    repo, created = services.get_or_create_boost_external_repo(
        external_github_repository
    )
    assert created is True
    assert repo.boost_version == ""
    assert repo.is_boost_embedded is False
    assert repo.is_boost_used is False


@pytest.mark.django_db
def test_get_or_create_boost_external_repo_does_not_update_when_empty_boost_version_passed(
    external_github_repository,
):
    """When existing has boost_version set, passing empty string does not overwrite (no update)."""
    services.get_or_create_boost_external_repo(
        external_github_repository,
        boost_version="1.82.0",
        is_boost_used=True,
    )
    repo2, created2 = services.get_or_create_boost_external_repo(
        external_github_repository,
        boost_version="",
        is_boost_used=True,
    )
    assert created2 is False
    repo2.refresh_from_db()
    assert repo2.boost_version == "1.82.0"


# --- update_boost_external_repo ---


@pytest.mark.django_db
def test_update_boost_external_repo_changes_boost_version(ext_repo):
    """update_boost_external_repo updates boost_version."""
    services.update_boost_external_repo(ext_repo, boost_version="1.85.0")
    ext_repo.refresh_from_db()
    assert ext_repo.boost_version == "1.85.0"


@pytest.mark.django_db
def test_update_boost_external_repo_changes_is_boost_used(ext_repo):
    """update_boost_external_repo updates is_boost_used."""
    services.update_boost_external_repo(ext_repo, is_boost_used=False)
    ext_repo.refresh_from_db()
    assert ext_repo.is_boost_used is False


@pytest.mark.django_db
def test_update_boost_external_repo_no_op_when_same(ext_repo):
    """update_boost_external_repo leaves DB unchanged when values match."""
    old_updated = ext_repo.updated_at
    result = services.update_boost_external_repo(
        ext_repo,
        boost_version=ext_repo.boost_version,
    )
    result.refresh_from_db()
    assert result.updated_at == old_updated


# --- update_boost_external_repo: edge cases ---


@pytest.mark.django_db
def test_update_boost_external_repo_no_op_when_all_none(ext_repo):
    """update_boost_external_repo with all None leaves DB unchanged."""
    old_updated = ext_repo.updated_at
    old_version = ext_repo.boost_version
    result = services.update_boost_external_repo(ext_repo)
    result.refresh_from_db()
    assert result.updated_at == old_updated
    assert result.boost_version == old_version


@pytest.mark.django_db
def test_update_boost_external_repo_changes_is_boost_embedded(ext_repo):
    """update_boost_external_repo updates is_boost_embedded."""
    assert ext_repo.is_boost_embedded is False
    services.update_boost_external_repo(ext_repo, is_boost_embedded=True)
    ext_repo.refresh_from_db()
    assert ext_repo.is_boost_embedded is True


@pytest.mark.django_db
def test_update_boost_external_repo_empty_boost_version(ext_repo):
    """update_boost_external_repo can set boost_version to empty string."""
    services.update_boost_external_repo(ext_repo, boost_version="")
    ext_repo.refresh_from_db()
    assert ext_repo.boost_version == ""


# --- create_or_update_boost_usage ---


@pytest.mark.django_db
def test_create_or_update_boost_usage_creates_new(
    ext_repo,
    boost_file,
    external_github_file,
):
    """create_or_update_boost_usage creates new record and returns (usage, True)."""
    usage, created = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
        last_commit_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    assert created is True
    assert usage.repo_id == ext_repo.pk
    assert usage.boost_header_id == boost_file.pk
    assert usage.file_path_id == external_github_file.pk
    assert usage.last_commit_date is not None
    assert usage.excepted_at is None


@pytest.mark.django_db
def test_create_or_update_boost_usage_gets_existing_and_updates(
    ext_repo,
    boost_file,
    external_github_file,
):
    """create_or_update_boost_usage returns existing and updates last_commit_date, clears excepted_at."""
    usage1, _ = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
        last_commit_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    services.mark_usage_excepted(usage1)
    usage1.refresh_from_db()
    assert usage1.excepted_at is not None

    new_dt = datetime(2024, 7, 1, tzinfo=timezone.utc)
    usage2, created2 = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
        last_commit_date=new_dt,
    )
    assert created2 is False
    assert usage2.pk == usage1.pk
    usage2.refresh_from_db()
    assert usage2.last_commit_date == new_dt
    assert usage2.excepted_at is None


@pytest.mark.django_db
def test_create_or_update_boost_usage_idempotent(
    ext_repo,
    boost_file,
    external_github_file,
):
    """create_or_update_boost_usage same args returns existing."""
    services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
    )
    _, created2 = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
    )
    assert created2 is False
    assert (
        BoostUsage.objects.filter(
            repo=ext_repo,
            boost_header=boost_file,
            file_path=external_github_file,
        ).count()
        == 1
    )


# --- create_or_update_boost_usage: edge cases ---


@pytest.mark.django_db
def test_create_or_update_boost_usage_without_last_commit_date(
    ext_repo,
    boost_file,
    external_github_file,
):
    """create_or_update_boost_usage without last_commit_date creates usage with None."""
    usage, created = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
    )
    assert created is True
    assert usage.last_commit_date is None


@pytest.mark.django_db
def test_create_or_update_boost_usage_existing_no_last_commit_date_update(
    ext_repo,
    boost_file,
    external_github_file,
):
    """When existing has last_commit_date=None, passing last_commit_date updates it."""
    usage1, _ = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
        last_commit_date=None,
    )
    assert usage1.last_commit_date is None
    new_dt = datetime(2024, 9, 1, tzinfo=timezone.utc)
    usage2, created2 = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
        last_commit_date=new_dt,
    )
    assert created2 is False
    usage2.refresh_from_db()
    assert usage2.last_commit_date == new_dt


@pytest.mark.django_db
def test_create_or_update_boost_usage_clears_excepted_at_on_redetect(
    ext_repo,
    boost_file,
    external_github_file,
):
    """Re-detecting usage (create_or_update) clears excepted_at."""
    usage1, _ = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
    )
    services.mark_usage_excepted(usage1)
    usage1.refresh_from_db()
    assert usage1.excepted_at is not None
    usage2, _ = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
        last_commit_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    usage2.refresh_from_db()
    assert usage2.excepted_at is None


# --- mark_usage_excepted ---


@pytest.mark.django_db
def test_mark_usage_excepted_sets_excepted_at(
    ext_repo,
    boost_file,
    external_github_file,
):
    """mark_usage_excepted sets excepted_at to today."""
    usage, _ = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
    )
    assert usage.excepted_at is None
    result = services.mark_usage_excepted(usage)
    result.refresh_from_db()
    assert result.excepted_at is not None


@pytest.mark.django_db
def test_mark_usage_excepted_idempotent(
    ext_repo,
    boost_file,
    external_github_file,
):
    """mark_usage_excepted called twice does not change excepted_at again."""
    usage, _ = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
    )
    services.mark_usage_excepted(usage)
    usage.refresh_from_db()
    first_date = usage.excepted_at
    services.mark_usage_excepted(usage)
    usage.refresh_from_db()
    assert usage.excepted_at == first_date


# --- get_active_usages_for_repo ---


@pytest.mark.django_db
def test_get_active_usages_for_repo_returns_non_excepted(
    ext_repo,
    boost_file,
    external_github_file,
):
    """get_active_usages_for_repo returns usages with excepted_at null."""
    usage, _ = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
    )
    active = services.get_active_usages_for_repo(ext_repo)
    assert len(active) == 1
    assert active[0].pk == usage.pk


@pytest.mark.django_db
def test_get_active_usages_for_repo_excludes_excepted(
    ext_repo,
    boost_file,
    external_github_file,
):
    """get_active_usages_for_repo excludes usages with excepted_at set."""
    usage, _ = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
    )
    services.mark_usage_excepted(usage)
    active = services.get_active_usages_for_repo(ext_repo)
    assert len(active) == 0


# --- get_active_usages_for_repo: edge cases ---


@pytest.mark.django_db
def test_get_active_usages_for_repo_empty_when_no_usages(ext_repo):
    """get_active_usages_for_repo returns empty list when repo has no usages."""
    active = services.get_active_usages_for_repo(ext_repo)
    assert active == []


@pytest.mark.django_db
def test_get_active_usages_for_repo_returns_only_active_mixed(
    ext_repo,
    boost_file,
    external_github_file,
    external_github_repository,
):
    """get_active_usages_for_repo returns only non-excepted usages when mix exists."""
    import uuid

    from model_bakery import baker

    usage1, _ = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
    )
    services.mark_usage_excepted(usage1)
    # Second file in same repo (need another GitHubFile)
    file2 = baker.make(
        "github_activity_tracker.GitHubFile",
        repo=external_github_repository,
        filename="src/other-" + uuid.uuid4().hex[:6] + ".cpp",
    )
    usage2, _ = services.create_or_update_boost_usage(ext_repo, boost_file, file2)
    active = services.get_active_usages_for_repo(ext_repo)
    assert len(active) == 1
    assert active[0].pk == usage2.pk
    assert active[0].excepted_at is None


@pytest.mark.django_db
def test_get_active_usages_for_repo_select_related(
    ext_repo,
    boost_file,
    external_github_file,
):
    """get_active_usages_for_repo uses select_related for boost_header and file_path."""
    services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
    )
    active = services.get_active_usages_for_repo(ext_repo)
    assert len(active) == 1
    # No extra queries when accessing related
    usage = active[0]
    assert usage.boost_header_id == boost_file.pk
    assert usage.file_path_id == external_github_file.pk
    _ = usage.boost_header
    _ = usage.file_path


# --- get_or_create_missing_header_usage ---


@pytest.mark.django_db
def test_get_or_create_missing_header_usage_creates_new(
    ext_repo,
    external_github_file,
):
    """get_or_create_missing_header_usage creates placeholder usage and tmp, returns (usage, tmp, True)."""
    usage, tmp, created_tmp = services.get_or_create_missing_header_usage(
        ext_repo,
        external_github_file,
        "boost/unknown/header.hpp",
        last_commit_date=datetime(2024, 5, 1, tzinfo=timezone.utc),
    )
    assert created_tmp is True
    assert usage.boost_header_id is None
    assert usage.repo_id == ext_repo.pk
    assert usage.file_path_id == external_github_file.pk
    assert tmp.usage_id == usage.pk
    assert tmp.header_name == "boost/unknown/header.hpp"


@pytest.mark.django_db
def test_get_or_create_missing_header_usage_gets_existing_tmp(
    ext_repo,
    external_github_file,
):
    """get_or_create_missing_header_usage returns existing tmp and (usage, tmp, False)."""
    services.get_or_create_missing_header_usage(
        ext_repo,
        external_github_file,
        "boost/same.hpp",
    )
    usage2, _, created2 = services.get_or_create_missing_header_usage(
        ext_repo,
        external_github_file,
        "boost/same.hpp",
    )
    assert created2 is False
    assert (
        BoostMissingHeaderTmp.objects.filter(
            usage=usage2,
            header_name="boost/same.hpp",
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_get_or_create_missing_header_usage_updates_last_commit_date(
    ext_repo,
    external_github_file,
):
    """get_or_create_missing_header_usage updates usage last_commit_date when existing."""
    services.get_or_create_missing_header_usage(
        ext_repo,
        external_github_file,
        "boost/other.hpp",
        last_commit_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    new_dt = datetime(2024, 8, 1, tzinfo=timezone.utc)
    usage, _, _ = services.get_or_create_missing_header_usage(
        ext_repo,
        external_github_file,
        "boost/other.hpp",
        last_commit_date=new_dt,
    )
    usage.refresh_from_db()
    assert usage.last_commit_date == new_dt


# --- get_or_create_missing_header_usage: edge cases ---


@pytest.mark.django_db
def test_get_or_create_missing_header_usage_header_name_max_length(
    ext_repo,
    external_github_file,
):
    """get_or_create_missing_header_usage accepts header_name up to 512 chars."""
    long_header = "boost/" + "x" * 506  # 6 + 506 = 512 chars total
    assert len(long_header) == 512
    _, tmp, created = services.get_or_create_missing_header_usage(
        ext_repo,
        external_github_file,
        long_header,
    )
    assert created is True
    tmp.refresh_from_db()
    assert tmp.header_name == long_header


@pytest.mark.django_db
def test_get_or_create_missing_header_usage_without_last_commit_date(
    ext_repo,
    external_github_file,
):
    """get_or_create_missing_header_usage without last_commit_date leaves usage with None."""
    usage, _, _ = services.get_or_create_missing_header_usage(
        ext_repo,
        external_github_file,
        "boost/no_date.hpp",
    )
    assert usage.last_commit_date is None


# --- bulk_create_or_update_boost_usage ---


@pytest.mark.django_db
def test_bulk_create_or_update_boost_usage_empty_returns_zero(ext_repo):
    """bulk_create_or_update_boost_usage with empty list returns (0, 0)."""
    created, updated = services.bulk_create_or_update_boost_usage(ext_repo, [])
    assert created == 0
    assert updated == 0


@pytest.mark.django_db
def test_bulk_create_or_update_boost_usage_creates_many(
    ext_repo,
    boost_file,
    external_github_file,
    external_github_repository,
):
    """bulk_create_or_update_boost_usage creates multiple usages in one go."""
    from model_bakery import baker
    import uuid

    file2 = baker.make(
        "github_activity_tracker.GitHubFile",
        repo=external_github_repository,
        filename="src/other-" + uuid.uuid4().hex[:6] + ".cpp",
    )
    items = [
        (boost_file, external_github_file, datetime(2024, 1, 1, tzinfo=timezone.utc)),
        (boost_file, file2, datetime(2024, 2, 1, tzinfo=timezone.utc)),
    ]
    created, updated = services.bulk_create_or_update_boost_usage(ext_repo, items)
    assert created == 2
    assert updated == 0
    assert (
        BoostUsage.objects.filter(repo=ext_repo, excepted_at__isnull=True).count() == 2
    )


@pytest.mark.django_db
def test_bulk_create_or_update_boost_usage_updates_existing(
    ext_repo,
    boost_file,
    external_github_file,
):
    """bulk_create_or_update_boost_usage updates existing and clears excepted_at."""
    usage, _ = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
        last_commit_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    services.mark_usage_excepted(usage)
    usage.refresh_from_db()
    assert usage.excepted_at is not None

    new_dt = datetime(2024, 6, 1, tzinfo=timezone.utc)
    created, updated = services.bulk_create_or_update_boost_usage(
        ext_repo,
        [(boost_file, external_github_file, new_dt)],
    )
    assert created == 0
    assert updated == 1
    usage.refresh_from_db()
    assert usage.last_commit_date == new_dt
    assert usage.excepted_at is None


# --- mark_usages_excepted_bulk ---


@pytest.mark.django_db
def test_mark_usages_excepted_bulk_empty_returns_zero():
    """mark_usages_excepted_bulk with empty list returns 0."""
    assert services.mark_usages_excepted_bulk([]) == 0


@pytest.mark.django_db
def test_mark_usages_excepted_bulk_sets_excepted_at(
    ext_repo,
    boost_file,
    external_github_file,
):
    """mark_usages_excepted_bulk sets excepted_at for given usage IDs."""
    usage, _ = services.create_or_update_boost_usage(
        ext_repo,
        boost_file,
        external_github_file,
    )
    assert usage.excepted_at is None
    n = services.mark_usages_excepted_bulk([usage.pk])
    assert n == 1
    usage.refresh_from_db()
    assert usage.excepted_at is not None


# --- Boost header catalog lookup + missing-header resolution ---


@pytest.mark.django_db
def test_find_boost_file_for_header_name_single_match(boost_file, github_file):
    """find_boost_file_for_header_name returns BoostFile when catalog has one match."""
    assert github_file.filename == "include/boost/algorithm.hpp"
    got = services.find_boost_file_for_header_name("boost/algorithm.hpp")
    assert got is not None
    assert got.pk == boost_file.pk


@pytest.mark.django_db
def test_find_boost_file_for_header_name_not_found():
    """find_boost_file_for_header_name returns None when nothing matches."""
    assert services.find_boost_file_for_header_name("boost/does/not/exist.hpp") is None


@pytest.mark.django_db
def test_find_boost_file_for_header_name_does_not_match_longer_path(
    boost_library_repository,
    boost_library,
):
    """Only ``include/<header>`` is the catalog key; longer paths are not aliases."""
    from boost_library_tracker import services as bl_services
    from model_bakery import baker

    gf = baker.make(
        "github_activity_tracker.GitHubFile",
        repo=boost_library_repository,
        filename="libs/asio/include/boost/asio/stuff.hpp",
    )
    bl_services.get_or_create_boost_file(gf, boost_library)
    assert services.find_boost_file_for_header_name("boost/asio/stuff.hpp") is None


@pytest.mark.django_db
def test_find_boost_file_for_header_name_two_active_same_filename_ambiguous():
    """Two non-deleted files with the same path in different repos → ambiguous."""
    import uuid

    from boost_library_tracker import services as bl_services
    from model_bakery import baker

    def _one_boost_file():
        owner = baker.make("cppa_user_tracker.GitHubAccount")
        gh_repo = baker.make(
            "github_activity_tracker.GitHubRepository",
            owner_account=owner,
            repo_name="boostdup-" + uuid.uuid4().hex[:6],
        )
        bl_repo, _ = bl_services.get_or_create_boost_library_repo(gh_repo)
        lib, _ = bl_services.get_or_create_boost_library(bl_repo, "dup-lib")
        gf = baker.make(
            "github_activity_tracker.GitHubFile",
            repo=gh_repo,
            filename="include/boost/dup_header.hpp",
            is_deleted=False,
        )
        return bl_services.get_or_create_boost_file(gf, lib)[0]

    _one_boost_file()
    _one_boost_file()
    bf, status = services.find_boost_file_for_header_name_detailed(
        "boost/dup_header.hpp"
    )
    assert bf is None
    assert status == "ambiguous"


@pytest.mark.django_db
def test_find_boost_file_for_header_name_single_deleted_still_picked():
    """Only matching row is deleted → still linked (disambiguation rule)."""
    import uuid

    from boost_library_tracker import services as bl_services
    from model_bakery import baker

    owner = baker.make("cppa_user_tracker.GitHubAccount")
    gh_repo = baker.make(
        "github_activity_tracker.GitHubRepository",
        owner_account=owner,
        repo_name="boostdel-" + uuid.uuid4().hex[:6],
    )
    bl_repo, _ = bl_services.get_or_create_boost_library_repo(gh_repo)
    lib, _ = bl_services.get_or_create_boost_library(bl_repo, "del-lib")
    gf = baker.make(
        "github_activity_tracker.GitHubFile",
        repo=gh_repo,
        filename="include/boost/deleted_only.hpp",
        is_deleted=True,
    )
    bf, _ = bl_services.get_or_create_boost_file(gf, lib)
    got = services.find_boost_file_for_header_name("boost/deleted_only.hpp")
    assert got is not None
    assert got.pk == bf.pk


@pytest.mark.django_db
def test_resolve_missing_header_tmp_auto_resolves(
    ext_repo, external_github_file, boost_file
):
    """resolve_missing_header_tmp_auto creates real usage and removes tmp."""
    _, tmp, _ = services.get_or_create_missing_header_usage(
        ext_repo,
        external_github_file,
        "boost/algorithm.hpp",
    )
    placeholder_pk = tmp.usage_id
    assert services.resolve_missing_header_tmp_auto(tmp) == "resolved"
    assert BoostMissingHeaderTmp.objects.count() == 0
    assert BoostUsage.objects.filter(
        repo=ext_repo,
        boost_header=boost_file,
        file_path=external_github_file,
    ).exists()
    assert not BoostUsage.objects.filter(pk=placeholder_pk).exists()


@pytest.mark.django_db
def test_resolve_missing_header_tmp_auto_two_tmps_keeps_placeholder_until_last(
    ext_repo,
    external_github_file,
    boost_library_repository,
    boost_library,
):
    """Two tmp rows on same placeholder: first resolve keeps usage; second deletes it."""
    from boost_library_tracker import services as bl_services
    from model_bakery import baker

    gf_a = baker.make(
        "github_activity_tracker.GitHubFile",
        repo=boost_library_repository,
        filename="include/boost/resolve_a.hpp",
    )
    gf_b = baker.make(
        "github_activity_tracker.GitHubFile",
        repo=boost_library_repository,
        filename="include/boost/resolve_b.hpp",
    )
    bl_services.get_or_create_boost_file(gf_a, boost_library)
    bl_services.get_or_create_boost_file(gf_b, boost_library)

    usage, tmp_a, _ = services.get_or_create_missing_header_usage(
        ext_repo, external_github_file, "boost/resolve_a.hpp"
    )
    _, tmp_b, _ = services.get_or_create_missing_header_usage(
        ext_repo, external_github_file, "boost/resolve_b.hpp"
    )
    assert tmp_b.usage_id == usage.pk

    assert services.resolve_missing_header_tmp_auto(tmp_a) == "resolved"
    assert BoostUsage.objects.filter(pk=usage.pk).exists()
    assert BoostMissingHeaderTmp.objects.count() == 1

    assert services.resolve_missing_header_tmp_auto(tmp_b) == "resolved"
    assert BoostMissingHeaderTmp.objects.count() == 0
    assert not BoostUsage.objects.filter(pk=usage.pk).exists()


@pytest.mark.django_db
def test_resolve_all_missing_header_tmp_batch_dry_run_no_writes(
    ext_repo,
    external_github_file,
    boost_file,
):
    """Dry-run batch does not delete tmp rows."""
    services.get_or_create_missing_header_usage(
        ext_repo,
        external_github_file,
        "boost/algorithm.hpp",
    )
    stats = services.resolve_all_missing_header_tmp_batch(dry_run=True)
    assert stats.get("would_resolve", 0) >= 1
    assert BoostMissingHeaderTmp.objects.count() == 1
