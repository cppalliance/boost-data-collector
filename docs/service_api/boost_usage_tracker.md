# boost_usage_tracker.services

**Module path:** `boost_usage_tracker.services`
**Description:** External repositories that use Boost, BoostUsage records, and temporary missing-header records. Single place for all writes to boost_usage_tracker models.

**Type notation:** Model types refer to `boost_usage_tracker.models`. Cross-app: `GitHubRepository`, `GitHubFile` are from `github_activity_tracker.models`; `BoostFile` is from `boost_library_tracker.models`.

---

## BoostExternalRepository

| Function                            | Parameter types                                                                                             | Return type                            | Raises |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------- | -------------------------------------- | ------ |
| `get_or_create_boost_external_repo` | `github_repository: GitHubRepository`, `boost_version=""`, `is_boost_embedded=False`, `is_boost_used=False` | `tuple[BoostExternalRepository, bool]` | —      |
| `update_boost_external_repo`        | `ext_repo: BoostExternalRepository`, `boost_version=None`, `is_boost_embedded=None`, `is_boost_used=None`   | `BoostExternalRepository`              | —      |

---

## BoostUsage

| Function                             | Parameter types                                                                     | Return type                                      | Raises |
| ------------------------------------ | ----------------------------------------------------------------------------------- | ------------------------------------------------ | ------ |
| `create_or_update_boost_usage`       | `repo`, `boost_header: BoostFile`, `file_path: GitHubFile`, `last_commit_date=None` | `tuple[BoostUsage, bool]`                        | —      |
| `mark_usage_excepted`                | `usage: BoostUsage`                                                                 | `BoostUsage`                                     | —      |
| `get_active_usages_for_repo`         | `repo: BoostExternalRepository`                                                     | `list[BoostUsage]`                               | —      |
| `get_or_create_missing_header_usage` | `repo`, `file_path: GitHubFile`, `header_name: str`, `last_commit_date=None`        | `tuple[BoostUsage, BoostMissingHeaderTmp, bool]` | —      |

**Note:** `get_or_create_missing_header_usage` creates or reuses a placeholder `BoostUsage` with `boost_header=None` and a `BoostMissingHeaderTmp` row for the unresolved `header_name`. Used when the header is not yet in BoostFile/GitHubFile.

---

## Boost header catalog lookup (read + disambiguation)

Catalog paths use `include/<header_path>` (see `boost_catalog_filename`). Lookup uses **only** an exact `GitHubFile.filename` match to that full path (e.g. `include/boost/asio.hpp`). Longer paths such as `libs/asio/include/boost/asio.hpp` are different files and are **not** matched via substring or `endswith`. When several `BoostFile` rows share the same `GitHubFile.filename` (e.g. across repos), resolution uses `GitHubFile.is_deleted`:

- Exactly one non-deleted match → that `BoostFile`.
- More than one non-deleted match → ambiguous (`None`).
- No non-deleted matches: exactly one candidate total (even if deleted) → that `BoostFile`; otherwise ambiguous or no match.

| Function                               | Parameter types                                      | Return type                                           | Raises |
| -------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------- | ------ |
| `boost_catalog_filename`               | `header_path: str`                                   | `str`                                                 | —      |
| `find_boost_file_for_header_name`      | `header_path: str`                                   | `BoostFile \| None`                                   | —      |
| `find_boost_file_for_header_name_detailed` | `header_path: str`                               | `tuple[BoostFile \| None, "found"\|"not_found"\|"ambiguous"]` | —      |
| `find_boost_files_exact_by_catalog_names` | `catalog_names: set[str]`                        | `dict[str, BoostFile \| None]`                        | —      |

---

## BoostMissingHeaderTmp resolution

| Function                              | Parameter types                    | Return type        | Raises |
| ------------------------------------- | ---------------------------------- | ------------------ | ------ |
| `delete_boost_missing_header_tmp`     | `tmp: BoostMissingHeaderTmp`       | `None`             | —      |
| `maybe_delete_placeholder_boost_usage_after_tmp_removed` | `usage_pk: int`         | `bool`             | —      |
| `resolve_missing_header_tmp_auto`     | `tmp: BoostMissingHeaderTmp`       | `str` (outcome tag)| —      |
| `resolve_all_missing_header_tmp_batch`| `dry_run: bool = False`            | `dict[str, int]`   | —      |

**Outcome tags for `resolve_missing_header_tmp_auto`:** `resolved`, `skipped_no_match`, `skipped_ambiguous`, `error`.

**Note:** `resolve_all_missing_header_tmp_batch` iterates all tmp rows. With `dry_run=True`, no DB writes; keys include `would_resolve`, `skipped_no_match`, `skipped_ambiguous`. Used before `monitor_content` in `run_boost_usage_tracker` and from Django admin actions.

---

## Related docs

- [Schema.md](../Schema.md) – Section 4: Boost Usage Tracker.
- [Contributing.md](../Contributing.md) – Service layer rule.
