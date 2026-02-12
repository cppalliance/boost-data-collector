"""
Fixtures for cppa_pinecone_sync app.

No app-specific fixtures required for basic model/service tests;
models are created via services or baker in tests.
"""

import pytest


@pytest.fixture
def sync_type():
    """Default sync_type for tests."""
    return "test_type"


@pytest.fixture
def failed_id_list():
    """Sample list of failed IDs for record_failed_ids tests."""
    return ["id1", "id2", "id3"]
