# clang_github_tracker.services

**Module path:** `clang_github_tracker.services`
**Description:** Upserts for `ClangGithubIssueItem` and `ClangGithubCommit` (no FKs to other apps). Used by `sync_clang_github_activity`, `backfill_clang_github_tracker`, and date resolution watermarks.

**Type notation:** Models live in `clang_github_tracker.models`.

---
<!-- SERVICE_API:GENERATED:START -->

## Public API (generated)

| Function | Parameters | Return type | Summary |
| --- | --- | --- | --- |
| `get_commit_watermark` |  | Optional[datetime] | Max ``github_committed_at`` across commits (API fetch cursor base). |
| `get_issue_item_watermark` |  | Optional[datetime] | Max ``github_updated_at`` across issues and PRs (API fetch cursor base). |
| `start_after_watermark` | max_dt: datetime \| None | datetime \| None | Return ``max + 1ms`` for API fetch lower bound, or ``None`` if no watermark. |
| `upsert_commit` | sha: str, *, github_committed_at: datetime \| None | tuple[ClangGithubCommit, bool] | Create or update a ClangGithubCommit by ``sha``. Returns (instance, created). |
| `upsert_commits_batch` | rows: Sequence[tuple[str, datetime \| None]], *, batch_size: int = DEFAULT_UPSERT_BATCH_SIZE | tuple[int, int] | Batch upsert commits by ``sha``. Skips rows whose sha is not 40 chars. |
| `upsert_issue_item` | number: int, *, is_pull_request: bool, github_created_at: datetime \| None, github_updated_at: datetime \| None | tuple[ClangGithubIssueItem, bool] | Create or update a ClangGithubIssueItem by ``number``. Returns (instance, created). |
| `upsert_issue_items_batch` | rows: Sequence[tuple[int, bool, datetime \| None, datetime \| None]], *, batch_size: int = DEFAULT_UPSERT_BATCH_SIZE | tuple[int, int] | Batch upsert issue/PR rows by ``number``. |

<!-- SERVICE_API:GENERATED:END -->

Used by `clang_github_tracker.state_manager.resolve_start_end_dates` (with optional CLI `--since` / `--until` bounds).

---

## Related docs

- [Schema.md](../Schema.md) – Section 2b: Clang GitHub Tracker.
- [Workspace.md](../Workspace.md) – `workspace/raw/github_activity_tracker/`, `workspace/clang_github_tracker/`.
- [CONTRIBUTING.md](../../CONTRIBUTING.md) – Service layer rule.
