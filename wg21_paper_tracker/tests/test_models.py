"""Tests for wg21_paper_tracker.models."""

from datetime import date

import pytest
from django.db import IntegrityError, transaction

from wg21_paper_tracker.models import WG21Mailing, WG21Paper


@pytest.mark.django_db
def test_wg21_mailing_str():
    """WG21Mailing.__str__ returns mailing_date and title."""
    m = WG21Mailing.objects.create(mailing_date="2025-01", title="2025-01 pre-meeting")
    assert str(m) == "2025-01 (2025-01 pre-meeting)"


@pytest.mark.django_db
def test_wg21_paper_str():
    """WG21Paper.__str__ returns paper_id and truncated title."""
    m = WG21Mailing.objects.create(mailing_date="2025-01", title="Title")
    p = WG21Paper.objects.create(
        paper_id="p1000r0",
        url="https://example.com/p.pdf",
        title="A short title",
        document_date=date(2025, 1, 15),
        mailing=m,
        year=2025,
    )
    assert "p1000r0" in str(p)
    assert "A short title" in str(p)


@pytest.mark.django_db
def test_wg21_paper_str_truncates_long_title():
    """WG21Paper.__str__ truncates title to 60 chars."""
    m = WG21Mailing.objects.create(mailing_date="2025-01", title="Title")
    long_title = "x" * 100
    p = WG21Paper.objects.create(
        paper_id="p1",
        url="https://example.com/p.pdf",
        title=long_title,
        mailing=m,
        year=2025,
    )
    assert len(str(p).split(": ", 1)[-1]) <= 60


@pytest.mark.django_db
def test_wg21_mailing_ordering():
    """WG21Mailing default ordering is by mailing_date descending."""
    WG21Mailing.objects.create(mailing_date="2025-01", title="A")
    WG21Mailing.objects.create(mailing_date="2025-02", title="B")
    dates = list(WG21Mailing.objects.values_list("mailing_date", flat=True))
    assert dates == ["2025-02", "2025-01"]


@pytest.mark.django_db
def test_wg21_paper_unique_together_paper_id_year():
    """WG21Paper allows same paper_id with different year; rejects duplicate (paper_id, year)."""
    m1 = WG21Mailing.objects.create(mailing_date="2024-11", title="M1")
    m2 = WG21Mailing.objects.create(mailing_date="2025-01", title="M2")
    WG21Paper.objects.create(
        paper_id="sd-1",
        url="https://example.com/1.pdf",
        title="T1",
        mailing=m1,
        year=2024,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            WG21Paper.objects.create(
                paper_id="sd-1",
                url="https://example.com/dup.pdf",
                title="T1 dup",
                mailing=m1,
                year=2024,
            )
    p2 = WG21Paper.objects.create(
        paper_id="sd-1",
        url="https://example.com/2.pdf",
        title="T2",
        mailing=m2,
        year=2025,
    )
    assert p2.pk is not None
