"""Tests for config.health readiness checks."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from boost_collector_runner import services as collector_services
from config.health import run_health_checks

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return Client()


@override_settings(HEALTH_COLLECTOR_STALE_HOURS=26)
def test_health_view_healthy_when_db_and_celery_ok(api_client):
    now = timezone.now()
    for gid in ("github", "slack", "mailing_list", "boost_library_docs"):
        collector_services.record_group_success(gid, when=now)
    with patch("config.health._check_celery_workers") as mock_celery:
        mock_celery.return_value = {
            "ok": True,
            "workers": ["celery@host"],
            "responded": 1,
            "expected": 1,
        }
        response = api_client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["checks"]["database"]["ok"] is True


@override_settings(
    HEALTH_COLLECTOR_STALE_HOURS=26,
    HEALTH_ENFORCE_COLLECTOR_FRESHNESS=True,
)
def test_health_view_503_when_stale_group(api_client):
    old = timezone.now() - timedelta(hours=48)
    collector_services.record_group_success("github", when=old)
    with patch("config.health._check_celery_workers") as mock_celery:
        mock_celery.return_value = {
            "ok": True,
            "workers": [],
            "responded": 1,
            "expected": 1,
        }
        with patch(
            "config.health._groups_with_daily_schedule", return_value={"github"}
        ):
            response = api_client.get("/health/")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"


@override_settings(HEALTH_CHECK_TOKEN="secret-token")
def test_health_view_requires_bearer_when_token_set(api_client):
    response = api_client.get("/health/")
    assert response.status_code == 401
    response = api_client.get("/health/", HTTP_AUTHORIZATION="Bearer secret-token")
    assert response.status_code in (200, 503)


def test_run_health_checks_celery_failure():
    with patch("config.health._check_celery_workers") as mock_celery:
        mock_celery.return_value = {
            "ok": False,
            "workers": [],
            "responded": 0,
            "expected": 1,
        }
        payload, status = run_health_checks()
    assert status == 503
    assert payload["checks"]["celery_workers"]["ok"] is False


def test_run_health_checks_db_failure_returns_json_not_500():
    with patch("config.health._check_database") as mock_db:
        mock_db.return_value = {"ok": False, "error": "connection refused"}
        with patch("config.health._check_celery_workers") as mock_celery:
            mock_celery.return_value = {
                "ok": True,
                "workers": ["celery@host"],
                "responded": 1,
                "expected": 1,
            }
            payload, status = run_health_checks()
    assert status == 503
    assert payload["status"] == "unhealthy"
    assert payload["checks"]["database"]["ok"] is False
    assert payload["checks"]["collector_groups"] == {}
