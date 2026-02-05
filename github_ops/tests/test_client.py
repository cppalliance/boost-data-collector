"""Tests for github_ops client (smoke / no-network where possible)."""
import pytest


def test_import_get_github_client():
    """github_ops.get_github_client is importable."""
    from github_ops import get_github_client
    assert callable(get_github_client)


def test_import_get_github_token():
    """github_ops.get_github_token is importable."""
    from github_ops import get_github_token
    assert callable(get_github_token)
