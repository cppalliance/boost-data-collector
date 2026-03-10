"""Tests for wg21_paper_tracker.workspace."""

from pathlib import Path
from unittest.mock import patch

import pytest

from wg21_paper_tracker.workspace import get_workspace_root, get_raw_dir


@pytest.fixture
def mock_workspace_path(tmp_path):
    """Patch get_workspace_path to return tmp_path for app slugs."""

    def _get_path(app_slug):
        p = tmp_path / app_slug.replace("/", "_")
        p.mkdir(parents=True, exist_ok=True)
        return p

    with patch(
        "wg21_paper_tracker.workspace.get_workspace_path",
        side_effect=_get_path,
    ):
        yield tmp_path


def test_get_workspace_root_returns_path(mock_workspace_path):
    """get_workspace_root returns Path for app workspace."""
    root = get_workspace_root()
    assert "wg21_paper_tracker" in str(root)
    assert root.is_dir()


def test_get_workspace_root_calls_get_workspace_path_with_slug():
    """get_workspace_root calls get_workspace_path with app slug."""
    with patch("wg21_paper_tracker.workspace.get_workspace_path") as m:
        m.return_value = Path("/fake/workspace/wg21_paper_tracker")
        root = get_workspace_root()
    m.assert_called_once_with("wg21_paper_tracker")
    assert root == Path("/fake/workspace/wg21_paper_tracker")


def test_get_raw_dir_returns_mailing_date_subdir(mock_workspace_path):
    """get_raw_dir returns raw/wg21_paper_tracker/<mailing_date>/."""
    with patch("wg21_paper_tracker.workspace.get_workspace_path") as m:
        raw_root = mock_workspace_path / "raw_wg21_paper_tracker"
        raw_root.mkdir(parents=True, exist_ok=True)
        m.side_effect = lambda slug: {
            "wg21_paper_tracker": mock_workspace_path / "wg21_paper_tracker",
            "raw/wg21_paper_tracker": raw_root,
        }[slug]
        path = get_raw_dir("2025-01")
    assert path == raw_root / "2025-01"
    assert path.is_dir()


def test_get_raw_dir_creates_parents(mock_workspace_path):
    """get_raw_dir creates parent directories."""
    with patch("wg21_paper_tracker.workspace.get_workspace_path") as m:
        raw_root = mock_workspace_path / "raw_app"
        raw_root.mkdir(parents=True, exist_ok=True)
        m.side_effect = lambda slug: (
            raw_root if "raw" in slug else (mock_workspace_path / "app")
        )
        path = get_raw_dir("2026-02")
    assert path.exists()
    assert path.name == "2026-02"


def test_get_raw_dir_idempotent(mock_workspace_path):
    """get_raw_dir can be called twice for same mailing_date without error."""
    with patch("wg21_paper_tracker.workspace.get_workspace_path") as m:
        raw_root = mock_workspace_path / "raw"
        raw_root.mkdir(parents=True, exist_ok=True)
        m.side_effect = lambda slug: raw_root
        p1 = get_raw_dir("2025-01")
        p2 = get_raw_dir("2025-01")
    assert p1 == p2
    assert p1.parent == p2.parent


def test_get_raw_dir_rejects_invalid_mailing_date():
    """get_raw_dir raises ValueError for non-YYYY-MM mailing_date (path traversal, etc.)."""
    with pytest.raises(ValueError, match="mailing_date must be in YYYY-MM format"):
        get_raw_dir("../../tmp")
    with pytest.raises(ValueError, match="mailing_date must be in YYYY-MM format"):
        get_raw_dir("2025")
    with pytest.raises(ValueError, match="mailing_date must be in YYYY-MM format"):
        get_raw_dir("2025-1")
    with pytest.raises(ValueError, match="mailing_date must be in YYYY-MM format"):
        get_raw_dir("2025-13")
    with pytest.raises(ValueError, match="mailing_date must be in YYYY-MM format"):
        get_raw_dir("2025-00")
    with pytest.raises(ValueError, match="mailing_date must be in YYYY-MM format"):
        get_raw_dir("")
