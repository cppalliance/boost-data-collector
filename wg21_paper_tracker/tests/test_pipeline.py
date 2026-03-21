"""Tests for wg21_paper_tracker.pipeline."""

from unittest.mock import patch

import pytest

from wg21_paper_tracker.pipeline import TrackerPipelineResult, run_tracker_pipeline


# --- run_tracker_pipeline ---


@pytest.mark.django_db
def test_run_tracker_pipeline_returns_empty_when_no_mailings():
    """run_tracker_pipeline returns empty result when fetch_all_mailings returns []."""
    with patch("wg21_paper_tracker.pipeline.fetch_all_mailings", return_value=[]):
        result = run_tracker_pipeline()
    assert result.new_paper_count == 0
    assert result.new_paper_urls == ()


@pytest.mark.django_db
def test_run_tracker_pipeline_skips_when_no_new_mailings():
    """run_tracker_pipeline returns empty when all mailings are <= latest in DB."""
    from wg21_paper_tracker.models import WG21Mailing

    WG21Mailing.objects.create(mailing_date="2025-02", title="Latest")
    with patch("wg21_paper_tracker.pipeline.fetch_all_mailings") as m:
        m.return_value = [
            {"mailing_date": "2025-01", "title": "Old", "year": "2025"},
            {"mailing_date": "2025-02", "title": "Latest", "year": "2025"},
        ]
        with patch(
            "wg21_paper_tracker.pipeline.fetch_papers_for_mailing", return_value=[]
        ):
            result = run_tracker_pipeline()
    assert result.new_paper_count == 0


@pytest.mark.django_db
def test_run_tracker_pipeline_collects_urls_for_new_papers():
    """run_tracker_pipeline returns URLs for papers created in this run."""
    from wg21_paper_tracker.models import WG21Mailing

    WG21Mailing.objects.create(mailing_date="2025-01", title="Previous")
    mailings = [
        {"mailing_date": "2025-01", "title": "Previous", "year": "2025"},
        {"mailing_date": "2025-02", "title": "New", "year": "2025"},
    ]
    papers = [
        {
            "paper_id": "p1000r0",
            "url": "https://example.com/p1000r0.pdf",
            "filename": "p1000r0.pdf",
            "title": "A paper",
            "type": "pdf",
            "authors": [],
            "document_date": None,
            "subgroup": "",
        },
    ]
    with patch("wg21_paper_tracker.pipeline.fetch_all_mailings", return_value=mailings):
        with patch(
            "wg21_paper_tracker.pipeline.fetch_papers_for_mailing", return_value=papers
        ):
            result = run_tracker_pipeline()
    assert result.new_paper_count == 1
    assert result.new_paper_urls == ("https://example.com/p1000r0.pdf",)


@pytest.mark.django_db
def test_run_tracker_pipeline_from_mailing_date_backfills_older_than_db_latest():
    """from_mailing_date includes mailings >= date even when DB latest is newer."""
    from wg21_paper_tracker.models import WG21Mailing

    WG21Mailing.objects.create(mailing_date="2025-02", title="Latest in DB")
    mailings = [
        {"mailing_date": "2025-01", "title": "Older", "year": "2025"},
        {"mailing_date": "2025-02", "title": "Latest in DB", "year": "2025"},
    ]
    papers = [
        {
            "paper_id": "p1111r0",
            "url": "https://example.com/p1111r0.pdf",
            "filename": "p1111r0.pdf",
            "title": "January paper",
            "type": "pdf",
            "authors": [],
            "document_date": None,
            "subgroup": "",
        },
    ]
    with patch("wg21_paper_tracker.pipeline.fetch_all_mailings", return_value=mailings):
        with patch(
            "wg21_paper_tracker.pipeline.fetch_papers_for_mailing", return_value=papers
        ):
            result = run_tracker_pipeline(from_mailing_date="2025-01")
    assert result.new_paper_count == 1
    assert result.new_paper_urls == ("https://example.com/p1111r0.pdf",)


@pytest.mark.django_db
def test_run_tracker_pipeline_second_run_no_new_urls():
    """Existing papers do not add URLs on a subsequent run."""
    from wg21_paper_tracker.models import WG21Mailing

    WG21Mailing.objects.create(mailing_date="2025-01", title="Previous")
    mailings = [
        {"mailing_date": "2025-02", "title": "New", "year": "2025"},
    ]
    papers = [
        {
            "paper_id": "p1000r0",
            "url": "https://example.com/p1000r0.pdf",
            "filename": "p1000r0.pdf",
            "title": "A paper",
            "type": "pdf",
            "authors": [],
            "document_date": None,
            "subgroup": "",
        },
    ]
    with patch("wg21_paper_tracker.pipeline.fetch_all_mailings", return_value=mailings):
        with patch(
            "wg21_paper_tracker.pipeline.fetch_papers_for_mailing", return_value=papers
        ):
            first = run_tracker_pipeline()
            second = run_tracker_pipeline()
    assert first.new_paper_count == 1
    assert second.new_paper_count == 0


def test_tracker_pipeline_result_count():
    """TrackerPipelineResult.new_paper_count matches tuple length."""
    r = TrackerPipelineResult(new_paper_urls=("a", "b"))
    assert r.new_paper_count == 2


def test_run_tracker_pipeline_rejects_bad_from_mailing_date():
    """from_mailing_date must look like YYYY-MM."""
    with pytest.raises(ValueError, match="Invalid from_mailing_date"):
        run_tracker_pipeline(from_mailing_date="not-valid")


def test_run_tracker_pipeline_rejects_bad_to_mailing_date():
    """to_mailing_date must look like YYYY-MM."""
    with pytest.raises(ValueError, match="Invalid to_mailing_date"):
        run_tracker_pipeline(to_mailing_date="not-valid")


@pytest.mark.django_db
def test_run_tracker_pipeline_rejects_from_after_to():
    with pytest.raises(ValueError, match="after"):
        run_tracker_pipeline(from_mailing_date="2025-03", to_mailing_date="2025-01")


@pytest.mark.django_db
def test_run_tracker_pipeline_to_mailing_date_caps_inclusive_range():
    """With from and to, mailings outside [from, to] are skipped."""
    from wg21_paper_tracker.models import WG21Mailing

    WG21Mailing.objects.create(mailing_date="2025-03", title="Latest in DB")
    mailings = [
        {"mailing_date": "2025-01", "title": "Too early", "year": "2025"},
        {"mailing_date": "2025-02", "title": "In range", "year": "2025"},
        {"mailing_date": "2025-03", "title": "In range", "year": "2025"},
        {"mailing_date": "2025-04", "title": "Too late", "year": "2025"},
    ]
    papers = [
        {
            "paper_id": "p2222r0",
            "url": "https://example.com/p2222r0.pdf",
            "filename": "p2222r0.pdf",
            "title": "Feb",
            "type": "pdf",
            "authors": [],
            "document_date": None,
            "subgroup": "",
        },
    ]
    with patch("wg21_paper_tracker.pipeline.fetch_all_mailings", return_value=mailings):
        with patch(
            "wg21_paper_tracker.pipeline.fetch_papers_for_mailing", return_value=papers
        ) as fetch:
            result = run_tracker_pipeline(
                from_mailing_date="2025-02", to_mailing_date="2025-03"
            )
    assert result.new_paper_count == 1
    assert fetch.call_count == 2


@pytest.mark.django_db
def test_run_tracker_pipeline_to_only_caps_incremental_above_latest():
    """to_mailing_date without from: still require mailing_date > latest_in_db."""
    from wg21_paper_tracker.models import WG21Mailing

    WG21Mailing.objects.create(mailing_date="2025-01", title="Latest")
    mailings = [
        {"mailing_date": "2025-01", "title": "Latest", "year": "2025"},
        {"mailing_date": "2025-02", "title": "New", "year": "2025"},
        {"mailing_date": "2025-03", "title": "Too new for cap", "year": "2025"},
    ]
    papers = [
        {
            "paper_id": "p3333r0",
            "url": "https://example.com/p3333r0.pdf",
            "filename": "p3333r0.pdf",
            "title": "A",
            "type": "pdf",
            "authors": [],
            "document_date": None,
            "subgroup": "",
        },
    ]
    with patch("wg21_paper_tracker.pipeline.fetch_all_mailings", return_value=mailings):
        with patch(
            "wg21_paper_tracker.pipeline.fetch_papers_for_mailing", return_value=papers
        ) as fetch:
            result = run_tracker_pipeline(to_mailing_date="2025-02")
    assert result.new_paper_count == 1
    assert fetch.call_count == 1
