"""
Management command for WG21 Paper Tracker.
Runs the pipeline to fetch new mailings, download papers, upload to GCS, and update DB.
If new papers were found and uploaded, it triggers the Google Cloud Run conversion job.
"""

import logging
import os
from django.core.management.base import BaseCommand
from django.conf import settings

from wg21_paper_tracker.pipeline import run_tracker_pipeline

logger = logging.getLogger(__name__)

def trigger_cloud_run_job(project_id: str, location: str, job_name: str):
    from google.cloud import run_v2
    client = run_v2.JobsClient()
    name = client.job_path(project_id, location, job_name)
    request = run_v2.RunJobRequest(name=name)
    logger.info("Triggering Cloud Run job %s...", name)
    operation = client.run_job(request=request)
    logger.info("Cloud Run job triggered. Operation: %s", operation.operation.name)
    return operation

class Command(BaseCommand):
    help = "Run WG21 paper tracker (fetch, download to GCS, DB update) and trigger Cloud Run if new papers."

    def handle(self, *args, **options):
        logger.info("Starting WG21 Paper Tracker...")
        
        try:
            total_new_papers = run_tracker_pipeline()
            self.stdout.write(self.style.SUCCESS(f"Downloaded and uploaded {total_new_papers} new papers."))
            
            if total_new_papers > 0:
                project_id = settings.GCP_PROJECT_ID
                location = settings.GCP_LOCATION
                job_name = settings.WG21_CLOUD_RUN_JOB_NAME

                if project_id and job_name:
                    try:
                        trigger_cloud_run_job(project_id, location, job_name)
                        self.stdout.write(self.style.SUCCESS(f"Successfully triggered Cloud Run job {job_name}."))
                    except Exception as e:
                        logger.error("Failed to trigger Cloud Run job: %s", e)
                        self.stderr.write(self.style.ERROR(f"Error triggering Cloud Run job: {e}"))
                else:
                    logger.warning("GCP_PROJECT_ID not configured. Skipping Cloud Run trigger.")
                    self.stdout.write(self.style.WARNING("Skipping Cloud Run trigger (missing GCP config)."))
            else:
                self.stdout.write("No new papers found. Skipping Cloud Run job.")
                
        except Exception as e:
            logger.exception("WG21 Paper Tracker failed: %s", e)
            raise
