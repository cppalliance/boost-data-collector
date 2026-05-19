# boost_usage_tracker.services

**Module path:** `boost_usage_tracker.services`
**Description:** External repositories that use Boost, BoostUsage records, and temporary missing-header records. Single place for all writes to boost_usage_tracker models.

**Type notation:** Model types refer to `boost_usage_tracker.models`. Cross-app: `GitHubRepository`, `GitHubFile` are from `github_activity_tracker.models`; `BoostFile` is from `boost_library_tracker.models`.

---
<!-- SERVICE_API:GENERATED:START -->

## Public API (generated)

| Function | Parameters | Return type | Summary |
| --- | --- | --- | --- |
| `bulk_create_or_update_boost_usage` | repo: BoostExternalRepository, items: list[tuple['BoostFile', 'GitHubFile', Optional[datetime]]] | tuple[int, int] | Create or update many BoostUsage rows in bulk. |
| `create_or_update_boost_usage` | repo: BoostExternalRepository, boost_header: 'BoostFile', file_path: 'GitHubFile', last_commit_date: Optional[datetime] = None | tuple[BoostUsage, bool] | Create or update a BoostUsage record. |
| `get_active_usages_for_repo` | repo: BoostExternalRepository | list[BoostUsage] | Return all active (non-excepted) BoostUsage records for *repo*. |
| `get_or_create_boost_external_repo` | github_repository: 'GitHubRepository', boost_version: str = '', is_boost_embedded: bool = False, is_boost_used: bool = False | tuple[BoostExternalRepository, bool] | Get or create BoostExternalRepository for a GitHubRepository (multi-table inheritance). |
| `get_or_create_missing_header_usage` | repo: BoostExternalRepository, file_path: 'GitHubFile', header_name: str, last_commit_date: Optional[datetime] = None | tuple[BoostUsage, BoostMissingHeaderTmp, bool] | Get or create a placeholder BoostUsage (boost_header=null) and a BoostMissingHeaderTmp. |
| `mark_usage_excepted` | usage: BoostUsage | BoostUsage | Mark a BoostUsage record as excepted (include no longer detected). |
| `mark_usages_excepted_bulk` | usage_ids: list[int] | int | Set excepted_at to today for multiple BoostUsage rows in one query. |
| `update_boost_external_repo` | ext_repo: BoostExternalRepository, boost_version: Optional[str] = None, is_boost_embedded: Optional[bool] = None, is_boost_used: Optional[bool] = None | BoostExternalRepository | Update mutable fields on an existing BoostExternalRepository. |

<!-- SERVICE_API:GENERATED:END -->

**Note:** `get_or_create_missing_header_usage` creates or reuses a placeholder `BoostUsage` with `boost_header=None` and a `BoostMissingHeaderTmp` row for the unresolved `header_name`. Used when the header is not yet in BoostFile/GitHubFile.

---

## Related docs

- [Schema.md](../Schema.md) – Section 4: Boost Usage Tracker.
- [CONTRIBUTING.md](../../CONTRIBUTING.md) – Service layer rule.
