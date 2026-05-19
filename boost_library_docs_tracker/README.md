# Boost Library Docs Tracker

## Overview

Fetches and converts **Boost library documentation** (HTML and related sources) into Markdown for storage and downstream search (Pinecone, etc.). Requires a working **`pandoc`** binary on the host (see root [README](../README.md#quick-start)).

## Data workflow

`run_boost_library_docs_tracker` crawls or unpacks documentation, normalizes it to Markdown, persists structured rows, then optionally **embeds the same content** into Pinecone. Service details: [docs/service_api/boost_library_docs_tracker.md](../docs/service_api/boost_library_docs_tracker.md).

### Where we fetch data

**Boost doc sources**: HTTP crawl of published library docs and/or a **downloaded Boost source archive** (`--use-local`), optionally scoped by `--library` and `--versions`. Release discovery may call the **GitHub API** when versions are not passed explicitly.

### How data is saved to the database

**`BoostDocContent`**, **`BoostLibraryDocumentation`**, and related rows hold page text, URLs, and crawl metadata. Converted Markdown and intermediate files are also written under **`WORKSPACE_DIR`** for auditing and reprocessing.

### How content is published to GitHub

**Not part of this app’s default pipeline.** Documentation is retained in PostgreSQL, the workspace, and (when enabled) Pinecone—not pushed as a standalone Markdown repo by this collector.

### How vectors sync to Pinecone

After DB + workspace writes, the collector can call **`run_cppa_pinecone_sync`** with this app’s preprocessor (unless `--skip-pinecone` or a dry run). That upserts into the namespace configured for Boost docs search; see [docs/Pinecone_preprocess_guideline.md](../docs/Pinecone_preprocess_guideline.md).

## Common tasks

- Run the tracker: `python manage.py run_boost_library_docs_tracker --help`.
- Service-layer overview: [docs/service_api/boost_library_docs_tracker.md](../docs/service_api/boost_library_docs_tracker.md).
- Confirm `pandoc` is on `PATH` before debugging conversion failures.

## Main command: `run_boost_library_docs_tracker`

Scrapes Boost library docs for one or more versions, writes workspace + `BoostDocContent` / `BoostLibraryDocumentation` rows, then upserts Pinecone (unless skipped).

| Option | Description |
| --- | --- |
| `--versions` | Zero or more Boost versions (e.g. `1.86.0 1.87.0`). **Omitted** → latest release from GitHub API. |
| `--library` | Limit scrape to one library key (e.g. `algorithm`). Default: all libraries for each version. |
| `--dry-run` | Parse/fetch without writing DB, workspace, or Pinecone. |
| `--skip-pinecone` | Write DB + workspace but skip Pinecone upsert. |
| `--max-pages` | Per-library BFS page cap when crawling HTTP (default **10**). |
| `--use-local` | Download Boost source zip and walk local HTML instead of HTTP crawl. |
| `--cleanup-extract` | With `--use-local`, delete extracted tree + downloaded zip after each version’s libraries finish. |

## Management commands

| Command | Purpose |
| --- | --- |
| `run_boost_library_docs_tracker` | Primary doc fetch / conversion pipeline. |

Run `python manage.py COMMAND --help` for options.

## Tests

```bash
python -m pytest boost_library_docs_tracker/tests/ -v
```

(from repo root; see root [README](../README.md#running-tests).)
