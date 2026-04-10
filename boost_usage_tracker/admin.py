from django.contrib import admin
from django.contrib.admin import ModelAdmin

from boost_usage_tracker import services as boost_usage_services

from .models import BoostExternalRepository, BoostMissingHeaderTmp, BoostUsage


@admin.register(BoostExternalRepository)
class BoostExternalRepositoryAdmin(ModelAdmin):
    list_display = (
        "id",
        "owner_account",
        "repo_name",
        "stars",
        "boost_version",
        "is_boost_embedded",
        "is_boost_used",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_boost_used", "is_boost_embedded", "created_at")
    search_fields = ("repo_name", "boost_version")
    raw_id_fields = ("owner_account",)


@admin.register(BoostUsage)
class BoostUsageAdmin(ModelAdmin):
    list_display = (
        "id",
        "repo",
        "boost_header",
        "file_path",
        "last_commit_date",
        "excepted_at",
        "created_at",
        "updated_at",
    )
    list_filter = ("excepted_at", "last_commit_date")
    search_fields = ("repo__repo_name",)
    raw_id_fields = ("repo", "boost_header", "file_path")


@admin.register(BoostMissingHeaderTmp)
class BoostMissingHeaderTmpAdmin(ModelAdmin):
    list_display = (
        "id",
        "header_name",
        "usage_repo",
        "usage_file_path",
        "usage",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = (
        "header_name",
        "usage__repo__repo_name",
        "usage__file_path__filename",
    )
    raw_id_fields = ("usage",)
    list_select_related = ("usage__repo__owner_account", "usage__file_path")
    actions = ("resolve_selected_if_in_catalog",)

    @admin.display(description="External repo", ordering="usage__repo__repo_name")
    def usage_repo(self, obj):
        r = obj.usage.repo
        return r.full_name if r else "—"

    @admin.display(description="File path", ordering="usage__file_path__filename")
    def usage_file_path(self, obj):
        fp = obj.usage.file_path
        return fp.filename if fp else "—"

    @admin.action(
        description="Resolve selected (if header exists in BoostFile catalog)"
    )
    def resolve_selected_if_in_catalog(self, request, queryset):
        counts: dict[str, int] = {}
        for tmp in queryset.select_related("usage__repo", "usage__file_path"):
            outcome = boost_usage_services.resolve_missing_header_tmp_auto(tmp)
            counts[outcome] = counts.get(outcome, 0) + 1
        parts = [
            f"resolved: {counts.get('resolved', 0)}",
            f"skipped (no catalog match): {counts.get('skipped_no_match', 0)}",
            f"skipped (ambiguous): {counts.get('skipped_ambiguous', 0)}",
            f"errors: {counts.get('error', 0)}",
        ]
        self.message_user(request, "; ".join(parts))
