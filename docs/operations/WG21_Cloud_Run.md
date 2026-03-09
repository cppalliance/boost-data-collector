# WG21 Paper Conversion Cloud Run Job

The PDF-to-Markdown conversion for WG21 papers is computationally heavy and requires system packages like `poppler`. It is separated from the main Django project and runs as a Google Cloud Run Job.

The Django tracker (`run_wg21_paper_tracker`) automatically triggers this job via the Google Cloud Run API when new papers are downloaded.

## 1. Setup Google Cloud Storage

Create a GCS bucket (e.g., `wg21-data-collector`).

Ensure your Django app has the following environment variables configured:
- `WG21_GCS_BUCKET`: The name of the GCS bucket.
- `GCP_PROJECT_ID`: Your GCP project ID.
- `WG21_CLOUD_RUN_JOB_NAME`: (Optional, defaults to `wg21-convert`) The name of the deployed Cloud Run job.
- `GCP_LOCATION`: (Optional, defaults to `us-central1`) Region for the Cloud Run job.

## 2. Build and Push the Docker Image

Navigate to the Cloud Run job directory:

```bash
cd wg21_paper_tracker/cloud_run_job/
```

Build the Docker image. Replace `[PROJECT_ID]` with your GCP Project ID:

```bash
docker build -t gcr.io/[PROJECT_ID]/wg21-convert .
```

Push the image to Google Container Registry (or Artifact Registry):

```bash
docker push gcr.io/[PROJECT_ID]/wg21-convert
```

## 3. Create the Cloud Run Job

Create the job in Google Cloud. We recommend allocating sufficient memory and CPU since Docling and PDFPlumber are resource-intensive.

```bash
gcloud run jobs create wg21-convert \
  --image gcr.io/[PROJECT_ID]/wg21-convert \
  --memory 8Gi \
  --cpu 4 \
  --region us-central1 \
  --set-env-vars WG21_GCS_BUCKET=wg21-data-collector,OPENROUTER_API_KEY=your_key
```

## 4. Service Account & IAM Permissions

1. **Tracker Permission:** The environment running the Django app (e.g., Celery worker or Scheduler) must run under a Service Account that has the `Cloud Run Invoker` (`roles/run.invoker`) role to trigger the job via the API.
2. **GCS Access:** Both the Django application and the Cloud Run job require read/write access to the GCS bucket (`roles/storage.objectAdmin`).

## 5. Flow Summary

1. **Daily (e.g. 1 AM)**: The `run_wg21_paper_tracker` command runs.
2. It checks the WG21 site for new mailings.
3. If found, it downloads PDFs and uploads them directly to `gs://<bucket>/raw/wg21_papers/<mailing_date>/`.
4. It calls the Cloud Run API to execute `wg21-convert`.
5. The Cloud Run Job spins up, reads the new PDFs from GCS, converts them, and uploads the `.md` results to `gs://<bucket>/converted/wg21_papers/<mailing_date>/`.
