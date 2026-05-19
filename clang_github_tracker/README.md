# Clang GitHub Tracker

## Overview

Collects **LLVM/Clang GitHub** activity (issues, PRs, commits) for configured repositories, similar in shape to `github_activity_tracker` but scoped to the Clang ecosystem. Uses shared `core.operations.github_ops` patterns.

## Common tasks

- Run the tracker: `python manage.py run_clang_github_tracker --help`.
- Repair or catch-up: `python manage.py backfill_clang_github_tracker --help`.
- Tokens and rate limits: root [README](../README.md#github-tokens) and [docs/operations/github.md](../docs/operations/github.md).

## Main command: `run_clang_github_tracker`

Fetches `llvm/llvm-project` activity into raw JSON + DB; optional Markdown export, remote push, and Pinecone. Resume uses **DB watermarks** (not `state.json`).

| Option | Description |
| --- | --- |
| `--dry-run` | No sync, export, push, or Pinecone; log resolved windows only. |
| `--skip-github-sync` | Skip API fetch / raw + DB upserts. |
| `--skip-markdown-export` | Skip `.md` export from this run’s results. |
| `--skip-remote-push` | Skip push to `CLANG_GITHUB_CONTEXT_REPO_*`. |
| `--skip-pinecone` | Skip `run_cppa_pinecone_sync` for issues/PRs. |
| `--since`, `--from-date`, `--start-time` | Sync window start (`YYYY-MM-DD` or ISO-8601). Aliases are equivalent. |
| `--until`, `--to-date`, `--end-time` | Sync window end; same formats as `--since`. |

### `backfill_clang_github_tracker`

Scans `raw/github_activity_tracker/<owner>/<repo>/commits|issues|prs/*.json` and upserts Clang DB rows. **No CLI options** beyond Django defaults—behavior is fully automatic from the raw tree.

## Management commands

| Command | Purpose |
| --- | --- |
| `run_clang_github_tracker` | Primary GitHub sync for Clang repos. |
| `backfill_clang_github_tracker` | Backfill or repair historical GitHub data. |

Run `python manage.py COMMAND --help` for options.

## Tests

```bash
python -m pytest clang_github_tracker/tests/ -v
```

(from repo root; see root [README](../README.md#running-tests).)
