"""Tests for clone_repo error paths (timeout / failure) with redacted exceptions."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from core.operations.github_ops import git_ops


@pytest.fixture
def fake_token():
    return "ghp_super_secret_do_not_leak"


@patch("core.operations.github_ops.git_ops.get_github_token", return_value="tok")
@patch("core.operations.github_ops.git_ops.subprocess.run")
def test_clone_repo_timeout_reraises_with_redacted_cmd(
    mock_run, _mock_token, tmp_path, fake_token
):
    mock_run.side_effect = subprocess.TimeoutExpired(
        cmd=["git", "clone", "x", str(tmp_path / "d")],
        timeout=1,
        output="out",
        stderr="err",
    )
    dest = tmp_path / "dest"
    with pytest.raises(subprocess.TimeoutExpired) as ei:
        git_ops.clone_repo("https://github.com/o/r.git", dest, token=fake_token)
    assert fake_token not in str(ei.value.cmd)


@patch("core.operations.github_ops.git_ops.get_github_token", return_value="tok")
@patch("core.operations.github_ops.git_ops.subprocess.run")
def test_clone_repo_called_process_error_reraises_sanitized_stderr(
    mock_run, _mock_token, tmp_path, fake_token
):
    mock_run.side_effect = subprocess.CalledProcessError(
        1,
        ["git", "clone"],
        output=None,
        stderr=f"fatal: auth failed x-access-token:{fake_token}\n",
    )
    dest = tmp_path / "dest2"
    with pytest.raises(subprocess.CalledProcessError) as ei:
        git_ops.clone_repo("o/r", dest, token=fake_token, depth=1)
    assert fake_token not in " ".join(ei.value.cmd)
    assert "--depth" in " ".join(ei.value.cmd)
