"""
Benchmark: GitHub-shaped commit payloads through sync path `_process_commit_data`.

Uses the unknown-author branch (no top-level author/committer) for stable
account resolution. Each payload includes one modified file with a unique path.
"""

from __future__ import annotations

import pytest

from github_activity_tracker.sync.commits import _process_commit_data


def _build_commit_payloads(n: int) -> list[dict]:
    """REST-shaped dicts compatible with `_process_commit_data` (no network)."""
    payloads: list[dict] = []
    for i in range(n):
        sha = f"b{i:039d}"  # 40 chars, unique per index
        fname = f"benchmarks/path_{i}/file.txt"
        payloads.append(
            {
                "sha": sha,
                "commit": {
                    "message": f"benchmark commit {i}\n",
                    "author": {
                        "name": "Bench User",
                        "email": "bench@example.invalid",
                        "date": "2024-01-01T12:00:00Z",
                    },
                },
                "files": [
                    {
                        "filename": fname,
                        "status": "modified",
                        "additions": 1,
                        "deletions": 1,
                        "patch": f"@@ benchmark {i} @@\n",
                    }
                ],
            }
        )
    return payloads


@pytest.mark.benchmark
@pytest.mark.django_db(transaction=True)
def test_process_commit_data_batch(
    benchmark,
    github_repository,
    benchmark_commit_n,
):
    n = benchmark_commit_n
    repo = github_repository
    payloads = _build_commit_payloads(n)

    def run_batch() -> None:
        for data in payloads:
            _process_commit_data(repo, data)

    benchmark.extra_info["n"] = n
    benchmark(run_batch)
