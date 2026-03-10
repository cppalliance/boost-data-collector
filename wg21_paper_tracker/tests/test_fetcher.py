"""Tests for wg21_paper_tracker.fetcher."""

from unittest.mock import patch, MagicMock

import requests

from wg21_paper_tracker.fetcher import (
    BASE_URL,
    fetch_all_mailings,
    fetch_papers_for_mailing,
)


# --- fetch_all_mailings ---


def test_fetch_all_mailings_returns_empty_on_request_failure():
    """fetch_all_mailings returns [] when requests.get raises RequestException."""
    with patch("wg21_paper_tracker.fetcher.requests.get") as m:
        m.side_effect = requests.RequestException("network error")
        result = fetch_all_mailings()
    assert result == []


def test_fetch_all_mailings_returns_empty_on_http_error():
    """fetch_all_mailings returns [] when response.raise_for_status raises HTTPError."""
    with patch("wg21_paper_tracker.fetcher.requests.get") as m:
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.HTTPError("404")
        m.return_value = resp
        result = fetch_all_mailings()
    assert result == []


def test_fetch_all_mailings_parses_links():
    """fetch_all_mailings parses year/#mailingYYYY-MM links and returns mailings."""
    html = """
    <html><body>
    <a href="2025/#mailing2025-01">2025-01 pre-meeting mailing</a>
    <a href="2025/#mailing2025-02">2025-02 post-meeting mailing</a>
    <a href="2024/#mailing2024-11">2024-11 mailing</a>
    <a href="other">Ignore</a>
    </body></html>
    """
    with patch("wg21_paper_tracker.fetcher.requests.get") as m:
        resp = MagicMock()
        resp.text = html
        resp.raise_for_status = MagicMock()
        m.return_value = resp
        result = fetch_all_mailings()
    assert len(result) == 3
    assert result[0]["mailing_date"] == "2025-01"
    assert result[0]["title"] == "2025-01 pre-meeting mailing"
    assert result[0]["year"] == "2025"
    assert result[1]["mailing_date"] == "2025-02"
    assert result[2]["mailing_date"] == "2024-11"
    assert result[2]["year"] == "2024"


def test_fetch_all_mailings_calls_index_url():
    """fetch_all_mailings calls BASE_URL/ with timeout."""
    with patch("wg21_paper_tracker.fetcher.requests.get") as m:
        m.return_value = MagicMock(text="<html></html>", raise_for_status=MagicMock())
        fetch_all_mailings()
    m.assert_called_once_with(f"{BASE_URL}/", timeout=30)


# --- fetch_papers_for_mailing ---


def test_fetch_papers_for_mailing_returns_empty_on_request_failure():
    """fetch_papers_for_mailing returns [] when requests.get raises RequestException."""
    with patch("wg21_paper_tracker.fetcher.requests.get") as m:
        m.side_effect = requests.RequestException("timeout")
        result = fetch_papers_for_mailing("2025", "2025-01")
    assert result == []


def test_fetch_papers_for_mailing_returns_empty_when_anchor_missing():
    """fetch_papers_for_mailing returns [] when mailing anchor is not found."""
    html = "<html><body><div id='other'>x</div></body></html>"
    with patch("wg21_paper_tracker.fetcher.requests.get") as m:
        resp = MagicMock()
        resp.text = html
        resp.raise_for_status = MagicMock()
        m.return_value = resp
        result = fetch_papers_for_mailing("2025", "2025-01")
    assert result == []


def test_fetch_papers_for_mailing_finds_anchor_by_id():
    """fetch_papers_for_mailing finds anchor by id=mailingYYYY-MM."""
    html = """
    <html><body>
    <span id="mailing2025-01"></span>
    <table>
    <tr><td><a href="p1000r0.pdf">p1000r0.pdf</a></td><td>Title</td><td>Author</td><td>2025-01-15</td><td>SG1</td></tr>
    </table>
    </body></html>
    """
    with patch("wg21_paper_tracker.fetcher.requests.get") as m:
        resp = MagicMock()
        resp.text = html
        resp.raise_for_status = MagicMock()
        m.return_value = resp
        result = fetch_papers_for_mailing("2025", "2025-01")
    assert len(result) == 1
    assert result[0]["paper_id"] == "p1000r0"
    assert result[0]["filename"] == "p1000r0.pdf"
    assert result[0]["title"] == "Title"
    assert result[0]["authors"] == ["Author"]
    assert result[0]["document_date"] == "2025-01-15"
    assert result[0]["subgroup"] == "SG1"


def test_fetch_papers_for_mailing_finds_anchor_by_name():
    """fetch_papers_for_mailing finds anchor by name= when id is missing."""
    html = """
    <html><body>
    <a name="mailing2025-01"></a>
    <table>
    <tr><td><a href="n5034.html">n5034.html</a></td><td>Draft</td></tr>
    </table>
    </body></html>
    """
    with patch("wg21_paper_tracker.fetcher.requests.get") as m:
        resp = MagicMock()
        resp.text = html
        resp.raise_for_status = MagicMock()
        m.return_value = resp
        result = fetch_papers_for_mailing("2025", "2025-01")
    assert len(result) == 1
    assert result[0]["paper_id"] == "n5034"
    assert result[0]["type"] == "html"


def test_fetch_papers_for_mailing_normalizes_paper_id_lowercase():
    """fetch_papers_for_mailing returns paper_id in lowercase."""
    html = """
    <html><body>
    <span id="mailing2025-01"></span>
    <table>
    <tr><td><a href="P3039R1.PDF">P3039R1.PDF</a></td></tr>
    </table>
    </body></html>
    """
    with patch("wg21_paper_tracker.fetcher.requests.get") as m:
        resp = MagicMock()
        resp.text = html
        resp.raise_for_status = MagicMock()
        m.return_value = resp
        result = fetch_papers_for_mailing("2025", "2025-01")
    assert result[0]["paper_id"] == "p3039r1"
    assert result[0]["filename"] == "p3039r1.pdf"


def test_fetch_papers_for_mailing_returns_empty_when_no_table():
    """fetch_papers_for_mailing returns [] when no table follows anchor."""
    html = """
    <html><body>
    <span id="mailing2025-01"></span>
    <p>No table here</p>
    </body></html>
    """
    with patch("wg21_paper_tracker.fetcher.requests.get") as m:
        resp = MagicMock()
        resp.text = html
        resp.raise_for_status = MagicMock()
        m.return_value = resp
        result = fetch_papers_for_mailing("2025", "2025-01")
    assert result == []


def test_fetch_papers_for_mailing_calls_year_url():
    """fetch_papers_for_mailing calls BASE_URL/{year}/ with timeout."""
    with patch("wg21_paper_tracker.fetcher.requests.get") as m:
        m.return_value = MagicMock(
            text="<html><body><span id='mailing2025-01'></span></body></html>",
            raise_for_status=MagicMock(),
        )
        fetch_papers_for_mailing("2025", "2025-01")
    m.assert_called_once_with(f"{BASE_URL}/2025/", timeout=30)
