from django.contrib import admin
from django.contrib.admin import ModelAdmin, TabularInline

from .models import (
    GitCommit,
    GitCommitFileChange,
    GitHubFile,
    GitHubRepository,
    Issue,
    IssueComment,
    IssueLabel,
    Language,
    License,
    PullRequest,
    PullRequestComment,
    PullRequestLabel,
    PullRequestReview,
    RepoLanguage,
)


@admin.register(Language)
class LanguageAdmin(ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)


@admin.register(License)
class LicenseAdmin(ModelAdmin):
    list_display = ("id", "name", "spdx_id", "created_at")
    search_fields = ("name", "spdx_id")


class RepoLanguageInline(TabularInline):
    """Languages use ``through=RepoLanguage``; edit links here, not as a raw M2M widget."""

    model = RepoLanguage
    extra = 0
    raw_id_fields = ("language",)


@admin.register(GitHubRepository)
class GitHubRepositoryAdmin(ModelAdmin):
    list_display = (
        "id",
        "full_name",
        "owner_account",
        "repo_name",
        "stars",
        "forks",
        "repo_pushed_at",
    )
    list_select_related = ("owner_account",)
    readonly_fields = ("full_name",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "full_name",
                    "owner_account",
                    "repo_name",
                    "stars",
                    "forks",
                    "description",
                    "repo_pushed_at",
                    "repo_created_at",
                    "repo_updated_at",
                ),
            },
        ),
        ("Relations", {"fields": ("licenses",)}),
    )
    inlines = (RepoLanguageInline,)
    list_filter = ("repo_created_at",)
    search_fields = ("repo_name", "description")
    raw_id_fields = ("owner_account",)


@admin.register(RepoLanguage)
class RepoLanguageAdmin(ModelAdmin):
    list_display = ("id", "repo", "language", "line_count", "updated_at")
    raw_id_fields = ("repo", "language")


@admin.register(GitCommit)
class GitCommitAdmin(ModelAdmin):
    list_display = ("id", "repo", "account", "commit_hash", "commit_at")
    list_filter = ("commit_at",)
    search_fields = ("commit_hash", "comment")
    raw_id_fields = ("repo", "account")


@admin.register(GitHubFile)
class GitHubFileAdmin(ModelAdmin):
    list_display = (
        "id",
        "filename",
        "repo_full_name",
        "previous_path",
        "is_deleted",
        "boost_library_name",
        "created_at",
    )
    list_filter = ("is_deleted",)
    search_fields = (
        "filename",
        "repo__repo_name",
        "repo__owner_account__username",
        "previous_filename__filename",
    )
    raw_id_fields = ("repo", "previous_filename")
    list_select_related = (
        "repo__owner_account",
        "previous_filename",
        "boost_file__library",
    )

    @admin.display(description="Repository", ordering="repo__repo_name")
    def repo_full_name(self, obj):
        return obj.repo.full_name if obj.repo_id else "—"

    @admin.display(description="Previous path")
    def previous_path(self, obj):
        if obj.previous_filename_id and obj.previous_filename:
            return obj.previous_filename.filename
        return "—"

    @admin.display(description="Boost library", ordering="boost_file__library__name")
    def boost_library_name(self, obj):
        bf = getattr(obj, "boost_file", None)
        if bf is not None and bf.library_id:
            return bf.library.name
        return "—"


@admin.register(GitCommitFileChange)
class GitCommitFileChangeAdmin(ModelAdmin):
    list_display = (
        "id",
        "commit",
        "github_file",
        "status",
        "additions",
        "deletions",
        "created_at",
    )
    list_filter = ("status",)
    raw_id_fields = ("commit", "github_file")


@admin.register(Issue)
class IssueAdmin(ModelAdmin):
    list_display = (
        "id",
        "repo",
        "account",
        "issue_number",
        "issue_id",
        "title",
        "state",
        "issue_created_at",
    )
    list_filter = ("state", "state_reason")
    search_fields = ("title", "body")
    raw_id_fields = ("repo", "account")
    filter_horizontal = ("assignees",)


@admin.register(IssueComment)
class IssueCommentAdmin(ModelAdmin):
    list_display = (
        "id",
        "issue",
        "account",
        "issue_comment_id",
        "issue_comment_created_at",
    )
    raw_id_fields = ("issue", "account")


@admin.register(IssueLabel)
class IssueLabelAdmin(ModelAdmin):
    list_display = ("id", "issue", "label_name", "created_at")
    list_filter = ("label_name",)
    raw_id_fields = ("issue",)


@admin.register(PullRequest)
class PullRequestAdmin(ModelAdmin):
    list_display = (
        "id",
        "repo",
        "account",
        "pr_number",
        "pr_id",
        "title",
        "state",
        "pr_created_at",
        "pr_merged_at",
    )
    list_filter = ("state",)
    search_fields = ("title", "body")
    raw_id_fields = ("repo", "account")
    filter_horizontal = ("assignees",)


@admin.register(PullRequestReview)
class PullRequestReviewAdmin(ModelAdmin):
    list_display = ("id", "pr", "account", "pr_review_id", "pr_review_created_at")
    raw_id_fields = ("pr", "account")


@admin.register(PullRequestComment)
class PullRequestCommentAdmin(ModelAdmin):
    list_display = ("id", "pr", "account", "pr_comment_id", "pr_comment_created_at")
    raw_id_fields = ("pr", "account")


@admin.register(PullRequestLabel)
class PullRequestLabelAdmin(ModelAdmin):
    list_display = ("id", "pr", "label_name", "created_at")
    list_filter = ("label_name",)
    raw_id_fields = ("pr",)
