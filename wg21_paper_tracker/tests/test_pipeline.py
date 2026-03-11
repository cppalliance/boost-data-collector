"""Tests for wg21_paper_tracker.pipeline."""

from unittest.mock import patch, MagicMock

import pytest
import requests

from wg21_paper_tracker.pipeline import (
    DOWNLOAD_TIMEOUT,
    DOWNLOAD_MAX_RETRIES,
    _download_file,
    run_tracker_pipeline,
)


# --- _download_file ---


def test_download_file_success_text(tmp_path):
    """_download_file saves text response and returns True."""
    url = "https://example.com/doc.html"
    filepath = tmp_path / "doc.html"
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.headers = {"content-type": "text/html; charset=utf-8"}
    resp.content = b"<html>Hello</html>"
    resp.apparent_encoding = "utf-8"
    resp.iter_content = None
    with patch("wg21_paper_tracker.pipeline.requests.get", return_value=resp):
        result = _download_file(url, filepath)
    assert result is True
    assert filepath.read_text(encoding="utf-8") == "<html>Hello</html>"


def test_download_file_success_binary(tmp_path):
    """_download_file saves binary response and returns True."""
    url = "https://example.com/doc.pdf"
    filepath = tmp_path / "doc.pdf"
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.headers = {"content-type": "application/pdf"}
    resp.iter_content = lambda chunk_size: (b"\x25\x50\x44\x46",)
    with patch("wg21_paper_tracker.pipeline.requests.get", return_value=resp):
        result = _download_file(url, filepath)
    assert result is True
    assert filepath.read_bytes() == b"\x25\x50\x44\x46"


def test_download_file_uses_timeout(tmp_path):
    """_download_file calls requests.get with DOWNLOAD_TIMEOUT."""
    url = "https://example.com/f"
    filepath = tmp_path / "out"
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.headers = {"content-type": "text/plain"}
    resp.content = b"x"
    resp.apparent_encoding = "utf-8"
    with patch("wg21_paper_tracker.pipeline.requests.get", return_value=resp) as m:
        _download_file(url, filepath)
    m.assert_called_once()
    assert m.call_args[1]["timeout"] == DOWNLOAD_TIMEOUT


def test_download_file_retries_on_failure(tmp_path):
    """_download_file retries up to DOWNLOAD_MAX_RETRIES then returns False."""
    url = "https://example.com/f"
    filepath = tmp_path / "f"
    with patch("wg21_paper_tracker.pipeline.requests.get") as m:
        m.side_effect = requests.RequestException("connection error")
        with patch("wg21_paper_tracker.pipeline.time.sleep") as sleep_mock:
            result = _download_file(url, filepath)
    assert result is False
    assert m.call_count == DOWNLOAD_MAX_RETRIES
    assert sleep_mock.call_count == DOWNLOAD_MAX_RETRIES - 1


def test_download_file_succeeds_on_second_attempt(tmp_path):
    """_download_file succeeds when a retry succeeds."""
    url = "https://example.com/f"
    filepath = tmp_path / "f"
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.headers = {"content-type": "text/plain"}
    resp.content = b"ok"
    resp.apparent_encoding = "utf-8"
    with patch("wg21_paper_tracker.pipeline.requests.get") as m:
        m.side_effect = [requests.RequestException("first fail"), resp]
        with patch("wg21_paper_tracker.pipeline.time.sleep"):
            result = _download_file(url, filepath)
    assert result is True
    assert m.call_count == 2
    assert filepath.read_text() == "ok"


# --- run_tracker_pipeline ---


@pytest.mark.django_db
def test_run_tracker_pipeline_returns_zero_when_no_mailings():
    """run_tracker_pipeline returns 0 when fetch_all_mailings returns []."""
    with patch("wg21_paper_tracker.pipeline.fetch_all_mailings", return_value=[]):
        n = run_tracker_pipeline()
    assert n == 0


@pytest.mark.django_db
def test_run_tracker_pipeline_skips_when_no_new_mailings():
    """run_tracker_pipeline returns 0 when all mailings are older than or equal to latest in DB."""
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
            n = run_tracker_pipeline()
    assert n == 0


@pytest.mark.django_db
def test_run_tracker_pipeline_downloads_new_papers(tmp_path):
    """run_tracker_pipeline downloads papers for new mailings and returns count."""
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
            with patch(
                "wg21_paper_tracker.pipeline.get_raw_dir", return_value=tmp_path
            ):
                with patch(
                    "wg21_paper_tracker.pipeline._download_file", return_value=True
                ):
                    with patch(
                        "wg21_paper_tracker.pipeline.settings.WG21_GCS_BUCKET",
                        "test-bucket",
                    ):
                        with patch(
                            "wg21_paper_tracker.pipeline._upload_to_gcs",
                            return_value=True,
                        ):
                            n = run_tracker_pipeline()
    assert n == 1
