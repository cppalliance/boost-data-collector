"""
Benchmark-only fixtures. Default pytest collection skips this directory unless
RUN_BENCHMARKS=1 (see root conftest.py).
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def benchmark_commit_n() -> int:
    """Number of commits / service rows per benchmark iteration (default tuned for CI)."""
    raw = os.environ.get("BENCHMARK_COMMIT_N", "50")
    n = int(raw)
    if n < 1:
        raise ValueError("BENCHMARK_COMMIT_N must be >= 1")
    return n
