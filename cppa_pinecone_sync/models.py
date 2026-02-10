"""
Models per docs/Schema.md section 9: CPPA Pinecone Sync.

PineconeFailList  – records failed sync operations by failed_id and type for retry or audit.
PineconeSyncStatus – tracks the last successful sync per source type.
"""

from django.db import models


class PineconeFailList(models.Model):
    """Records failed sync operations by failed_id and type for retry or audit."""

    failed_id = models.CharField(max_length=255, db_index=True)
    type = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cppa_pinecone_sync_pineconefaillist"
        ordering = ["id"]
        verbose_name = "Pinecone fail list entry"
        verbose_name_plural = "Pinecone fail list entries"

    def __str__(self) -> str:
        return f"PineconeFailList(type={self.type}, failed_id={self.failed_id})"


class PineconeSyncStatus(models.Model):
    """Tracks the last successful sync per source type.

    One row per type (e.g. slack, mailing_list, wg21).
    final_sync_at is when the last sync for that type completed.
    """

    type = models.CharField(max_length=64, unique=True, db_index=True)
    final_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cppa_pinecone_sync_pineconesyncstatus"
        ordering = ["type"]
        verbose_name = "Pinecone sync status"
        verbose_name_plural = "Pinecone sync statuses"

    def __str__(self) -> str:
        return (
            f"PineconeSyncStatus(type={self.type}, final_sync_at={self.final_sync_at})"
        )
