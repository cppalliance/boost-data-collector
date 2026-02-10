"""
Service layer for cppa_pinecone_sync.

All creates/updates/deletes for this app's models must go through functions in this
module. Do not call Model.objects.create(), model.save(), or model.delete() from
outside this module (e.g. from management commands, views, or other apps).

See docs/Contributing.md for the project-wide rule.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from django.utils import timezone

from .models import PineconeFailList, PineconeSyncStatus


# --- PineconeFailList ---


def get_failed_ids(sync_type: str) -> list[str]:
    """Return all failed_id values for the given type."""
    return list(
        PineconeFailList.objects.filter(type=sync_type).values_list(
            "failed_id", flat=True
        )
    )


def clear_failed_ids(sync_type: str) -> int:
    """Delete all PineconeFailList records for the given type. Returns count deleted."""
    count, _ = PineconeFailList.objects.filter(type=sync_type).delete()
    return count


def record_failed_ids(sync_type: str, failed_ids: list[str]) -> list[PineconeFailList]:
    """Bulk-create PineconeFailList entries for each failed_id. Returns created objects."""
    if not failed_ids:
        return []
    objs = [PineconeFailList(failed_id=fid, type=sync_type) for fid in failed_ids]
    return PineconeFailList.objects.bulk_create(objs)


# --- PineconeSyncStatus ---


def get_final_sync_at(sync_type: str) -> Optional[datetime]:
    """Return final_sync_at for the given type, or None if no record exists."""
    row = PineconeSyncStatus.objects.filter(type=sync_type).first()
    return row.final_sync_at if row else None


def update_sync_status(
    sync_type: str, final_sync_at: Optional[datetime] = None
) -> PineconeSyncStatus:
    """Create or update PineconeSyncStatus for the given type.

    Sets final_sync_at to the provided value, or now() if not given.
    Returns the PineconeSyncStatus instance.
    """
    ts = final_sync_at or timezone.now()
    obj, created = PineconeSyncStatus.objects.get_or_create(
        type=sync_type,
        defaults={"final_sync_at": ts},
    )
    if not created:
        obj.final_sync_at = ts
        obj.save(update_fields=["final_sync_at"])
    return obj
