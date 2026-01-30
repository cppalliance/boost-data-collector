# Boost Data Collector - Django project

## Overview

Boost Data Collector is a Django project that collects and manages data from various Boost-related sources. The project has multiple Django apps in one repository. All apps share one virtual environment, one database (PostgreSQL), and the same Django settings. Each app exposes one or more management commands (e.g. `run_boost_library_tracker`). The main workflow runs these commands in a fixed order (e.g. via `python manage.py run_all_collectors` or a Celery task). See [docs/Workflow.md](docs/Workflow.md) for workflow details.

## Quick start

### Prerequisites

- Python 3.11+
- Django (version in `requirements.txt`)
- PostgreSQL database access
- Environment variables for database URL and API keys (e.g. via `.env`)

### Initial setup

1. Clone the repository:

```bash
git clone <boost-data-collector-repo-url>
cd boost-data-collector
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure environment variables (e.g. copy `.env.example` to `.env` and set database URL and API credentials).

5. Run migrations:

```bash
python manage.py migrate
```

6. Run a single app command or the full workflow to confirm the project works:

```bash
python manage.py run_boost_library_tracker
# or run all collectors
python manage.py run_all_collectors
```

For local development you can also start the dev server: `python manage.py runserver`.

## Project structure

```
boost-data-collector/
├── manage.py
├── requirements.txt
├── .env.example
├── README.md
├── config/ or <project_name>/   # Django project settings (settings.py)
├── docs/                         # Documentation
│   ├── Workflow.md
│   ├── Schema.md
│   └── Development_guideline.md
└── [Django apps]/
    ├── boost_library_tracker/
    │   └── management/commands/
    ├── boost_usage_tracker/
    ├── boost_mailing_list_tracker/
    └── ...
```

Each Django app can expose management commands in `management/commands/` (e.g. `run_boost_library_tracker.py`). All apps are in `INSTALLED_APPS` and use the shared database.

## How it works

- Django project: One Django project with multiple Django apps; all apps share the same settings and database.
- Workflow: The main task runs app commands in a fixed order (e.g. `run_all_collectors` or a Celery task). Scheduling is done with Celery Beat or by running commands by hand.
- Database: One PostgreSQL database (e.g. `boost_dashboard`); Django ORM and migrations for all apps.
- Configuration: Django settings (`settings.py`) and environment variables (e.g. via `django-environ` or `python-decouple`).

## Documentation

- [Workflow.md](docs/Workflow.md) - Main application workflow, execution order, and project details.
- [Schema.md](docs/Schema.md) - Database schema and table relationships.
- [Development_guideline.md](docs/Development_guideline.md) - Development setup, app requirements, and step-by-step workflow.

## Branching strategy

- master: Main/production branch (stable code).
- develop: Development branch (active development).
- Feature branches: Created from `develop`. Developers must branch from `develop`; do not branch from `master`.
- Pull requests: Open pull requests against the `develop` branch.
