# Django project configuration (`config`)

## Overview

This package is the Django **project** layer: [`settings.py`](settings.py) (including `INSTALLED_APPS`, database, logging, and integration env vars), [`urls.py`](urls.py), [`wsgi.py`](wsgi.py) / [`asgi.py`](asgi.py), and the **Celery** app in [`celery.py`](celery.py). Collector scheduling for production is driven by [`boost_collector_schedule.yaml`](boost_collector_schedule.yaml) and executed through **`boost_collector_runner`** (see the root [README](../README.md) and [docs/Workflow.md](../docs/Workflow.md)).

## Common tasks

- Apply settings in code: `from django.conf import settings` (do not import `config.settings` directly in apps).
- Adjust schedule groups: edit `boost_collector_schedule.yaml`, then run Beat/worker as in the root README **Celery** section.
- Celery broker/result backend: set `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` in `.env` (see [.env.example](../.env.example)).
