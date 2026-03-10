"""Tests for wg21_paper_tracker.services."""

from datetime import date
from unittest.mock import patch

import pytest

from wg21_paper_tracker.services import (
    get_or_create_mailing,
    get_or_create_paper,
    mark_paper_downloaded,
)


# --- get_or_create_mailing ---


@pytest.mark.django_db
def test_get_or_create_mailing_creates_new():
    """get_or_create_mailing creates new mailing and returns (mailing, True)."""
    m, created = get_or_create_mailing("2025-01", "2025-01 pre-meeting mailing")
    assert created is True
    assert m.mailing_date == "2025-01"
    assert m.title == "2025-01 pre-meeting mailing"


@pytest.mark.django_db
def test_get_or_create_mailing_gets_existing():
    """get_or_create_mailing returns existing mailing and (mailing, False)."""
    get_or_create_mailing("2025-01", "Original title")
    m2, created2 = get_or_create_mailing("2025-01", "Updated title")
    assert created2 is False
    assert m2.mailing_date == "2025-01"
    assert m2.title == "Updated title"  # title is updated when different


@pytest.mark.django_db
def test_get_or_create_mailing_updates_title_when_different():
    """get_or_create_mailing updates title when existing has different title."""
    get_or_create_mailing("2025-02", "Old title")
    m, _ = get_or_create_mailing("2025-02", "New title")
    m.refresh_from_db()
    assert m.title == "New title"


# --- get_or_create_paper ---


@pytest.mark.django_db
@patch("wg21_paper_tracker.services.get_or_create_wg21_paper_author_profile")
def test_get_or_create_paper_creates_new(mock_profile, db):
    """get_or_create_paper creates new paper and returns (paper, True)."""
    mailing, _ = get_or_create_mailing("2025-01", "Title")
    paper, created = get_or_create_paper(
        paper_id="p1000r0",
        url="https://example.com/p1000r0.pdf",
        title="A paper",
        document_date=date(2025, 1, 15),
        mailing=mailing,
        subgroup="SG1",
        author_names=None,
        year=2025,
    )
    assert created is True
    assert paper.paper_id == "p1000r0"
    assert paper.title == "A paper"
    assert paper.year == 2025
    assert paper.mailing_id == mailing.id
    assert paper.subgroup == "SG1"
    mock_profile.assert_not_called()


@pytest.mark.django_db
@patch("wg21_paper_tracker.services.get_or_create_wg21_paper_author_profile")
def test_get_or_create_paper_calls_author_profile_for_each_author(mock_profile, db):
    """get_or_create_paper calls get_or_create_wg21_paper_author_profile for each author name."""
    from unittest.mock import MagicMock

    profile = MagicMock()
    profile.pk = 1
    mock_profile.return_value = (profile, True)

    mailing, _ = get_or_create_mailing("2025-01", "Title")
    with patch(
        "wg21_paper_tracker.services.WG21PaperAuthor.objects.get_or_create"
    ) as mock_link:
        mock_link.return_value = (MagicMock(), True)
        paper, created = get_or_create_paper(
            paper_id="p1000r0",
            url="https://example.com/p1000r0.pdf",
            title="A paper",
            document_date=None,
            mailing=mailing,
            author_names=["Alice", "Bob"],
            year=2025,
        )
    assert created is True
    assert mock_profile.call_count == 2
    mock_profile.assert_any_call("Alice")
    mock_profile.assert_any_call("Bob")


@pytest.mark.django_db
def test_get_or_create_paper_normalizes_paper_id_lowercase(db):
    """get_or_create_paper stores paper_id in lowercase."""
    mailing, _ = get_or_create_mailing("2025-01", "Title")
    paper, _ = get_or_create_paper(
        paper_id="  P3039R1  ",
        url="https://example.com/p3039r1.pdf",
        title="T",
        document_date=None,
        mailing=mailing,
        year=2025,
    )
    assert paper.paper_id == "p3039r1"


@pytest.mark.django_db
def test_get_or_create_paper_gets_existing_and_updates(db):
    """get_or_create_paper returns existing and updates fields when different."""
    mailing1, _ = get_or_create_mailing("2025-01", "M1")
    mailing2, _ = get_or_create_mailing("2025-02", "M2")
    get_or_create_paper(
        paper_id="p1000r0",
        url="https://example.com/old.pdf",
        title="Old title",
        document_date=date(2025, 1, 1),
        mailing=mailing1,
        subgroup="SG1",
        year=2025,
    )
    paper2, created2 = get_or_create_paper(
        paper_id="p1000r0",
        url="https://example.com/new.pdf",
        title="New title",
        document_date=date(2025, 2, 1),
        mailing=mailing2,
        subgroup="SG2",
        year=2025,
    )
    assert created2 is False
    paper2.refresh_from_db()
    assert paper2.url == "https://example.com/new.pdf"
    assert paper2.title == "New title"
    assert paper2.mailing_id == mailing2.id
    assert paper2.subgroup == "SG2"


@pytest.mark.django_db
def test_get_or_create_paper_year_none_stored_as_null(db):
    """get_or_create_paper with year=None stores null."""
    mailing, _ = get_or_create_mailing("2025-01", "Title")
    paper, _ = get_or_create_paper(
        paper_id="n5034",
        url="https://example.com/n5034.html",
        title="Draft",
        document_date=None,
        mailing=mailing,
        year=None,
    )
    assert paper.year is None


@pytest.mark.django_db
def test_get_or_create_paper_same_paper_id_different_year_creates_two(db):
    """get_or_create_paper creates separate rows for same paper_id different year (unique_together)."""
    mailing1, _ = get_or_create_mailing("2024-11", "M1")
    mailing2, _ = get_or_create_mailing("2025-01", "M2")
    p1, c1 = get_or_create_paper(
        paper_id="sd-1",
        url="https://example.com/sd-1-2024.pdf",
        title="SD 2024",
        document_date=None,
        mailing=mailing1,
        year=2024,
    )
    p2, c2 = get_or_create_paper(
        paper_id="sd-1",
        url="https://example.com/sd-1-2025.pdf",
        title="SD 2025",
        document_date=None,
        mailing=mailing2,
        year=2025,
    )
    assert c1 is True and c2 is True
    assert p1.pk != p2.pk
    assert p1.year == 2024 and p2.year == 2025


# --- mark_paper_downloaded ---


@pytest.mark.django_db
def test_mark_paper_downloaded_sets_flag(db):
    """mark_paper_downloaded sets is_downloaded=True for matching paper_id."""
    mailing, _ = get_or_create_mailing("2025-01", "Title")
    paper, _ = get_or_create_paper(
        paper_id="p1000r0",
        url="https://example.com/p.pdf",
        title="T",
        document_date=None,
        mailing=mailing,
        year=2025,
    )
    assert paper.is_downloaded is False
    mark_paper_downloaded("p1000r0")
    paper.refresh_from_db()
    assert paper.is_downloaded is True


@pytest.mark.django_db
def test_mark_paper_downloaded_normalizes_paper_id(db):
    """mark_paper_downloaded matches case-insensitively (normalizes to lower)."""
    mailing, _ = get_or_create_mailing("2025-01", "Title")
    paper, _ = get_or_create_paper(
        paper_id="p1000r0",
        url="https://example.com/p.pdf",
        title="T",
        document_date=None,
        mailing=mailing,
        year=2025,
    )
    mark_paper_downloaded("  P1000R0  ")
    paper.refresh_from_db()
    assert paper.is_downloaded is True
