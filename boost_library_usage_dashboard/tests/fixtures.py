"""Fixtures for boost_library_usage_dashboard tests."""

import pytest


@pytest.fixture
def dashboard_cmd_name():
    """Name of the ``run_boost_library_usage_dashboard`` management command."""
    return "run_boost_library_usage_dashboard"
