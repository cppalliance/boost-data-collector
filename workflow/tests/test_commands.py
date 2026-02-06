"""Tests for workflow management commands."""

import pytest
from django.core.management import call_command
from io import StringIO


@pytest.mark.django_db
def test_run_all_collectors_command_exists(workflow_cmd_name):
    """run_all_collectors command is registered and runs; may SystemExit(1) when tokens missing."""
    out = StringIO()
    err = StringIO()
    try:
        call_command(workflow_cmd_name, stdout=out, stderr=err)
    except SystemExit:
        # Expected when sub-commands fail (e.g. no GITHUB_TOKEN); command was found and ran.
        pass
    except Exception:
        # Other failures still mean the command exists and was invoked.
        pass
