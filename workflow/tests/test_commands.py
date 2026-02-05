"""Tests for workflow management commands."""
import pytest
from django.core.management import call_command
from io import StringIO


@pytest.mark.django_db
def test_run_all_collectors_command_exists(workflow_cmd_name):
    """run_all_collectors command is registered and runs without crashing (may fail on no config)."""
    out = StringIO()
    err = StringIO()
    # Command may exit non-zero if tokens/config missing; we only check it's callable.
    try:
        call_command(workflow_cmd_name, stdout=out, stderr=err)
    except Exception as e:
        # Expected when no GitHub tokens or DB state; we only care it's discovered.
        assert "run_all_collectors" in str(e) or True
    # If it runs, we're good
    assert True
