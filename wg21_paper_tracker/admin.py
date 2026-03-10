from django.contrib import admin
from wg21_paper_tracker.models import WG21Mailing, WG21Paper, WG21PaperAuthor


@admin.register(WG21Mailing)
class WG21MailingAdmin(admin.ModelAdmin):
    list_display = ("mailing_date", "title", "created_at", "updated_at")
    search_fields = ("mailing_date", "title")
    ordering = ("-mailing_date",)


class WG21PaperAuthorInline(admin.TabularInline):
    model = WG21PaperAuthor
    extra = 1
    raw_id_fields = ("profile",)


@admin.register(WG21Paper)
class WG21PaperAdmin(admin.ModelAdmin):
    list_display = (
        "paper_id",
        "year",
        "title",
        "document_date",
        "mailing",
        "subgroup",
        "is_downloaded",
    )
    search_fields = ("paper_id", "title", "url", "subgroup")
    list_filter = ("is_downloaded", "subgroup", "mailing", "year")
    ordering = ("-document_date", "-paper_id")
    inlines = [WG21PaperAuthorInline]


@admin.register(WG21PaperAuthor)
class WG21PaperAuthorAdmin(admin.ModelAdmin):
    list_display = ("paper", "profile", "created_at")
    search_fields = ("paper__paper_id", "profile__display_name")
    raw_id_fields = ("paper", "profile")
