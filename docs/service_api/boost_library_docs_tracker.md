# boost_library_docs_tracker.services

**Module path:** `boost_library_docs_tracker.services`
**Description:** Boost library docs content storage and (library-version, page) relation tracking with scrape/sync status. Single place for all writes to `boost_library_docs_tracker` models.

**Type notation:** `BoostDocContent` and `BoostLibraryDocumentation` are from `boost_library_docs_tracker.models`. `BoostLibraryVersion` is from `boost_library_tracker.models` (read-only cross-app reference).

**Pinecone upsert state** is stored on `BoostDocContent.is_upserted`, not on `BoostLibraryDocumentation` (the join table has only the two FKs plus `created_at`).

---
<!-- SERVICE_API:GENERATED:START -->

## Public API (generated)

| Function | Parameters | Return type | Summary |
| --- | --- | --- | --- |
| `get_docs_for_library_version` | library_version_id: int | django_models.QuerySet | Return all BoostLibraryDocumentation rows for this library-version. |
| `get_or_create_doc_content` | url: str, content_hash: str, version_id: int \| None = None | tuple[BoostDocContent, str] | Get or create a BoostDocContent row for the given content_hash. Page content is NOT stored in the DB; it lives in workspace files. |
| `get_unupserted_doc_contents` |  | django_models.QuerySet | Return all BoostDocContent rows that have not been upserted to Pinecone. |
| `link_content_to_library_version` | library_version_id: int, doc_content_id: int | tuple[BoostLibraryDocumentation, bool] | Get or create a BoostLibraryDocumentation row for the (library_version, doc_content) pair. Returns (relation, created). |
| `set_doc_content_upserted` | doc: BoostDocContent, value: bool | BoostDocContent | Set is_upserted on a BoostDocContent row. |
| `set_doc_content_upserted_by_ids` | ids: list[int], value: bool | int | Bulk-set is_upserted for BoostDocContent rows with the given PKs. Returns the number of rows updated. |

<!-- SERVICE_API:GENERATED:END -->

### `get_or_create_doc_content` return values

The second element is a `str` indicating what changed:

| `change_type` | Condition                     | Side effects                                                                    |
| ------------- | ----------------------------- | ------------------------------------------------------------------------------- |
| `"created"`   | `content_hash` not in DB      | Inserts row with `url`, `content_hash`, `scraped_at=now()`, `is_upserted=False`. May set `first_version_id` / `last_version_id` when `version_id` is passed. |
| `"unchanged"` | `content_hash` already exists | Updates `scraped_at`, and may update `url` and version FKs; same hash identity. |

---

## BoostLibraryDocumentation

Join table: one row per `(boost_library_version, boost_doc_content)` pair. **No** `page_count`, status fields, or `updated_at` on the model.

See the generated **Public API** table above for `link_content_to_library_version` and `get_docs_for_library_version`.
