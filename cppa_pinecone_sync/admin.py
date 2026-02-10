from django.contrib import admin
from django.contrib.admin import ModelAdmin

from .models import PineconeFailList, PineconeSyncStatus


@admin.register(PineconeFailList)
class PineconeFailListAdmin(ModelAdmin):
    list_display = ("id", "type", "failed_id", "created_at")
    list_filter = ("type", "created_at")
    search_fields = ("failed_id", "type")


@admin.register(PineconeSyncStatus)
class PineconeSyncStatusAdmin(ModelAdmin):
    list_display = ("id", "type", "final_sync_at", "created_at", "updated_at")
    list_filter = ("type",)
    search_fields = ("type",)
