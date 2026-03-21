# WG21 Paper Tracker → GitHub Actions (`repository_dispatch`)

The Django app **`run_wg21_paper_tracker`** scrapes WG21 mailings and stores paper metadata in the database. It does **not** download PDFs or other documents. When **new** paper rows are created in a run, it can send **one** [repository dispatch](https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event) to another GitHub repository so a workflow there fetches each URL and runs conversion (e.g. PDF → Markdown).

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `WG21_GITHUB_DISPATCH_ENABLED` | No (default `false`) | Set to `true` to send `repository_dispatch` when there are new papers. |
| `WG21_GITHUB_DISPATCH_REPO` | Yes, if enabled | Target repo as `owner/repo` (the repo whose workflow will run). |
| `WG21_GITHUB_DISPATCH_TOKEN` | Yes, if enabled | PAT or token with permission to create repository dispatch events on that repo (classic PAT: `repo` scope for private repos). |
| `WG21_GITHUB_DISPATCH_EVENT_TYPE` | No | Must match `on.repository_dispatch.types` in the target workflow. Default: `wg21_papers_convert`. |

## `client_payload` contract

The JSON body includes only a list of URL strings:

```json
{
  "papers": [
    "https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2025/…",
    "https://www.open-std.org/…"
  ]
}
```

- **`papers`**: array of strings (WG21 document URLs), all new papers from **that** pipeline run in a **single** event.
- There is **no** `new_paper_count` field; use `length(papers)` in the workflow if needed.

## Target repository workflow (example)

```yaml
on:
  repository_dispatch:
    types: [wg21_papers_convert]

jobs:
  convert:
    runs-on: ubuntu-latest
    steps:
      - name: URLs
        run: |
          echo '${{ toJson(github.event.client_payload.papers) }}'
      # Fetch each URL, convert, store artifacts / upload elsewhere
```

In expressions, `github.event.client_payload.papers` is a JSON array of strings.

## Token security

Store `WG21_GITHUB_DISPATCH_TOKEN` in a secret manager or CI secret—never commit it. Prefer a fine-grained PAT scoped to the conversion repo if possible.

## Payload size

Very large mailings could produce many URLs in one payload. If you approach GitHub or runner limits, document a split strategy (multiple dispatches) as an edge case; the default is one dispatch per tracker run with the full list.

## CLI options

- **`--from-date YYYY-MM`**: Process mailings with `mailing_date >= YYYY-MM` (WG21 / CSV style). Backfills from that key onward when used alone.
- **`--to-date YYYY-MM`**: Upper bound: `mailing_date <= YYYY-MM`. With `--from-date`, the run uses the inclusive range `[from, to]`. Without `--from-date`, behavior stays incremental (only mailings **newer than** the latest `WG21Mailing` in the DB), but capped at `to`—useful to avoid pulling very new mailings in a controlled run.
- **`--dry-run`**: Log only; do not run the pipeline or send dispatch.

## Flow summary

1. Scheduler runs `run_wg21_paper_tracker` (optionally with `--from-date` / `--to-date`).
2. Pipeline fetches mailings, upserts `WG21Mailing` / `WG21Paper` (metadata only).
3. For each row **newly created** in that run, its document URL is collected.
4. If the list is non-empty and dispatch is enabled, the app POSTs once to `POST /repos/{owner}/{repo}/dispatches` with `event_type` and `client_payload: { "papers": [ ... ] }`.
5. The conversion repo’s workflow runs and downloads each URL.
