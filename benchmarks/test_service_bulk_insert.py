"""
Benchmark: service-layer writes for N commits plus one file change each, in one transaction.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from django.db import transaction

from github_activity_tracker import services
from github_activity_tracker.models import FileChangeStatus


@pytest.mark.benchmark
@pytest.mark.django_db(transaction=True)
def test_service_bulk_commits_and_file_changes(
    benchmark,
    github_repository,
    github_account,
    benchmark_commit_n,
):
    n = benchmark_commit_n
    repo = github_repository
    account = github_account
    commit_at = datetime(2024, 6, 1, tzinfo=timezone.utc)
    hashes = [f"svcbulk{i:056d}"[:40] for i in range(n)]

    def run_batch() -> None:
        with transaction.atomic():
            for i in range(n):
                commit_obj, _ = services.create_or_update_commit(
                    repo=repo,
                    account=account,
                    commit_hash=hashes[i],
                    comment=f"svc bulk {i}",
                    commit_at=commit_at,
                )
                github_file, _ = services.create_or_update_github_file(
                    repo,
                    f"benchmarks/svc_bulk_{i}.txt",
                    is_deleted=False,
                )
                services.add_commit_file_change(
                    commit_obj,
                    github_file,
                    status=FileChangeStatus.MODIFIED,
                    additions=1,
                    deletions=0,
                    patch="",
                )

    benchmark.extra_info["n"] = n
    benchmark(run_batch)
