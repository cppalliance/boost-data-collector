"""
Management command: collect_boost_libraries

Collects all Boost library names from boostorg/boost and persists them as
BoostLibrary rows. Fetches .gitmodules to find libs/ submodules, then
meta/libraries.json from each submodule at the given ref via raw URLs:

  https://raw.githubusercontent.com/boostorg/boost/{ref}/.gitmodules
  https://raw.githubusercontent.com/boostorg/{submodule_name}/{ref}/meta/libraries.json

No doc-extension fetching. Intended to run after run_boost_library_tracker
has synced repos (submodules are not fetched again here).
"""
import logging

import requests
from django.core.management.base import BaseCommand

from boost_library_tracker.models import BoostLibraryRepository
from boost_library_tracker.parsing import (
    parse_gitmodules_lib_submodules,
    parse_libraries_json_library_names,
)
from boost_library_tracker.services import get_or_create_boost_library

logger = logging.getLogger(__name__)

MAIN_OWNER = "boostorg"
MAIN_REPO = "boost"
DEFAULT_REF = "develop"

RAW_GITMODULES_URL = "https://raw.githubusercontent.com/boostorg/boost/{ref}/.gitmodules"
RAW_LIBS_JSON_URL = (
    "https://raw.githubusercontent.com/boostorg/{submodule_name}/{ref}/meta/libraries.json"
)
FETCH_TIMEOUT = 30


def _fetch_raw_url(url: str) -> bytes | None:
    """Fetch URL and return response body, or None on failure."""
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        return resp.content
    except requests.RequestException as e:
        logger.warning("Fetch failed %s: %s", url, e)
        return None


def _collect_libraries_for_ref(ref: str) -> tuple[int, int]:
    """
    Fetch .gitmodules from boostorg/boost at ref, then for each lib submodule
    fetch meta/libraries.json from raw URL and create BoostLibrary records.
    Uses existing BoostLibraryRepository rows (no submodule sync).

    Returns (libraries_created, submodules_processed).
    """
    gitmodules_url = RAW_GITMODULES_URL.format(ref=ref)
    content = _fetch_raw_url(gitmodules_url)
    if not content:
        return 0, 0
    gitmodules_text = content.decode("utf-8")
    lib_submodules = parse_gitmodules_lib_submodules(gitmodules_text)

    created_total = 0
    for submodule_name, _path_in_boost in lib_submodules:
        boost_repo = (
            BoostLibraryRepository.objects.filter(
                owner_account__login=MAIN_OWNER,
                repo_name=submodule_name,
            )
            .first()
        )
        if not boost_repo:
            logger.debug(
                "Skipping submodule %s: no BoostLibraryRepository (run run_boost_library_tracker first)",
                submodule_name,
            )
            continue

        libs_json_url = RAW_LIBS_JSON_URL.format(
            submodule_name=submodule_name, ref=ref
        )
        raw = _fetch_raw_url(libs_json_url)
        if not raw:
            continue
        names = parse_libraries_json_library_names(raw, submodule_name)
        for name in names:
            _, created = get_or_create_boost_library(boost_repo, name)
            if created:
                created_total += 1

    return created_total, len(lib_submodules)


class Command(BaseCommand):
    help = (
        "Collect all Boost libraries from boostorg/boost: read .gitmodules at ref, "
        "then meta/libraries.json per lib submodule, and create BoostLibrary rows. "
        "Requires repos to exist (run run_boost_library_tracker first). No doc extensions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--ref",
            default=DEFAULT_REF,
            help=f"Branch/tag for .gitmodules and meta/libraries.json (default: {DEFAULT_REF}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only fetch and parse; do not create BoostLibrary rows.",
        )

    def handle(self, *args, **options):
        ref = (options.get("ref") or DEFAULT_REF).strip()
        dry_run = options.get("dry_run", False)

        self.stdout.write(
            f"Collecting Boost libraries at ref={ref} (dry_run={dry_run})..."
        )

        if dry_run:
            url = RAW_GITMODULES_URL.format(ref=ref)
            content = _fetch_raw_url(url)
            if not content:
                self.stdout.write(self.style.WARNING("No .gitmodules content."))
                return
            lib_submodules = parse_gitmodules_lib_submodules(content.decode("utf-8"))
            self.stdout.write(
                f"Would process {len(lib_submodules)} lib submodules (no DB writes)."
            )
            return

        created, num_submodules = _collect_libraries_for_ref(ref)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created} new BoostLibrary row(s) across {num_submodules} lib submodules."
            )
        )
