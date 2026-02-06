"""Minimal view tests (admin is the only app-served URL). Uses django-test-plus tp fixture."""

import pytest


@pytest.mark.django_db
def test_admin_login_redirect(tp):
    """GET /admin/ redirects to login (302) when not authenticated."""
    tp.get("/admin/")
    tp.response_302()


@pytest.mark.django_db
def test_admin_login_page_reachable(tp):
    """GET /admin/login/ returns 200."""
    tp.get("/admin/login/")
    tp.response_200()
