"""
Management command for WG21 Paper Tracker.
Runs the pipeline to fetch new mailings, download papers, upload to GCS, and update DB.
If new papers were found and uploaded, it triggers the Google Cloud Run conversion job.
"""

import logging
from django.core.management.base import BaseCommand
from django.conf import settings

from wg21_paper_tracker.pipeline import run_tracker_pipeline

logger = logging.getLogger(__name__)


def trigger_cloud_run_job(project_id: str, location: str, job_name: str):
    """
    Start the named Cloud Run job (run once, no polling).

    Uses the Cloud Run v2 API to trigger the job identified by project_id,
    location, and job_name. The job runs asynchronously; this function returns
    the operation and does not wait for the job to finish.
    """
    from google.cloud import run_v2

    client = run_v2.JobsClient()
    name = client.job_path(project_id, location, job_name)
    request = run_v2.RunJobRequest(name=name)
    logger.info("Triggering Cloud Run job %s...", name)
    operation = client.run_job(request=request)
    logger.info("Cloud Run job triggered. Operation: %s", operation.operation.name)
    return operation


class Command(BaseCommand):
    """Run WG21 paper tracker and optionally trigger the Cloud Run conversion job."""

    help = "Run WG21 paper tracker (fetch, download to GCS, DB update) and trigger Cloud Run if new papers."

    def add_arguments(self, parser):
        """Register --dry-run so the command can skip pipeline and Cloud Run."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only log what would be done; do not run the pipeline or trigger Cloud Run.",
        )

    def handle(self, *args, **options):
        """
        Run the tracker pipeline; if new papers were uploaded, trigger the Cloud Run job.

        With --dry-run, logs and exits without running the pipeline or triggering Cloud Run.
        Otherwise runs the pipeline, then triggers the configured Cloud Run job when
        total_new_papers > 0, WG21_CLOUD_RUN_ENABLED is True, and
        GCP_PROJECT_ID, WG21_CLOUD_RUN_JOB_NAME, and WG21_GCS_BUCKET are set.
        """
        dry_run = options.get("dry_run", False)
        if dry_run:
            logger.info("Dry run: skipping pipeline and Cloud Run trigger.")
            return

        logger.info("Starting WG21 Paper Tracker...")

        try:
            total_new_papers = run_tracker_pipeline()
            logger.info("Processed %d new papers.", total_new_papers)

            if total_new_papers > 0:
                project_id = getattr(settings, "GCP_PROJECT_ID", None)
                location = getattr(settings, "GCP_LOCATION", "us-central1")
                job_name = getattr(settings, "WG21_CLOUD_RUN_JOB_NAME", None)
                bucket = getattr(settings, "WG21_GCS_BUCKET", None)
                cloud_run_enabled = getattr(settings, "WG21_CLOUD_RUN_ENABLED", False)

                if project_id and job_name and bucket and cloud_run_enabled:
                    try:
                        trigger_cloud_run_job(project_id, location, job_name)
                        logger.info(
                            "Successfully triggered Cloud Run job %s.", job_name
                        )
                    except Exception:
                        logger.exception(
                            "Failed to trigger Cloud Run job %s.", job_name
                        )
                        raise
                else:
                    logger.warning(
                        "Skipping Cloud Run trigger: set WG21_CLOUD_RUN_ENABLED=True "
                        "and configure GCP_PROJECT_ID, WG21_CLOUD_RUN_JOB_NAME, and "
                        "WG21_GCS_BUCKET to enable."
                    )
            else:
                logger.info("No new papers found. Skipping Cloud Run job.")

        except Exception as e:
            logger.exception("WG21 Paper Tracker failed: %s", e)
            raise
