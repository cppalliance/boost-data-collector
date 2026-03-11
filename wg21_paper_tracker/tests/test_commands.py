"""Tests for wg21_paper_tracker management commands."""

import pytest
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError


CMD_NAME = "import_wg21_metadata_from_csv"


def test_import_wg21_metadata_from_csv_raises_when_csv_missing(tmp_path):
    """Command raises CommandError when CSV file does not exist."""
    csv_path = tmp_path / "nonexistent.csv"
    assert not csv_path.exists()

    with pytest.raises(CommandError, match=r"File not found:"):
        call_command(CMD_NAME, f"--csv-file={csv_path}")
