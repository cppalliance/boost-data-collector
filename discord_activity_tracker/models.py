from django.db import models

from cppa_user_tracker.models import DiscordProfile


class DiscordServer(models.Model):
    """Persisted Discord guild (server) metadata synced from export or API pipelines.

    One row per Discord guild snowflake ``server_id``. Holds display ``server_name``
    and optional ``icon_url`` for UI or audit. Timestamps ``created_at`` /
    ``updated_at`` track row lifecycle.

    Relationships:
        Reverse ``channels``: ``DiscordChannel`` rows with FK to this server
        (``related_name="channels"`` on ``DiscordChannel``).
    """

    server_id = models.BigIntegerField(unique=True, db_index=True)
    server_name = models.CharField(max_length=255, db_index=True)
    icon_url = models.URLField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["server_name"]

    def __str__(self):
        return f"{self.server_name} ({self.server_id})"


class DiscordChannel(models.Model):
    """A channel (text thread, category child, etc.) belonging to one ``DiscordServer``.

    Key fields: ``channel_id`` (Discord snowflake, globally unique), ``channel_name``,
    ``channel_type`` (e.g. exporter string), ``topic``, ``position``, and optional
    ``category_id`` / ``category_name`` for grouping in the guild tree.

    Relationships:
        ``server``: FK to ``DiscordServer`` (column ``server_id``).
        Reverse ``messages``: ``DiscordMessage`` rows for this channel
        (``related_name="messages"`` on ``DiscordMessage``).
    """

    server = models.ForeignKey(
        DiscordServer,
        on_delete=models.CASCADE,
        related_name="channels",
        db_column="server_id",
    )
    channel_id = models.BigIntegerField(unique=True, db_index=True)
    channel_name = models.CharField(max_length=255, db_index=True)
    channel_type = models.CharField(max_length=50)  # GuildTextChat, text, etc.
    # Category the channel belongs to (from DiscordChatExporter: categoryId / category)
    category_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    category_name = models.CharField(max_length=255, blank=True)
    topic = models.TextField(blank=True)
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["server", "position", "channel_name"]
        indexes = [
            models.Index(fields=["server", "channel_name"]),
        ]

    def __str__(self):
        return f"#{self.channel_name}"


class DiscordMessage(models.Model):
    """A single Discord message stored for search, export, and Pinecone preprocessing.

    Key fields: ``message_id`` (snowflake, unique), ``content``, ``message_type``
    (e.g. ``Default``, ``Reply``), ``is_pinned``, ``message_created_at`` /
    ``message_edited_at``, ``reply_to_message_id``, ``attachment_urls`` (JSON list),
    ``has_attachments``, and soft-delete flags ``is_deleted`` / ``deleted_at``.

    Relationships:
        ``channel``: FK to ``DiscordChannel`` (column ``channel_id``).
        ``author``: FK to ``DiscordProfile`` (``cppa_user_tracker.models``); column
        ``author_id``. Reverse on profile: ``discord_messages``.
        Reverse ``reactions``: ``DiscordReaction`` rows
        (``related_name="reactions"`` on ``DiscordReaction``).

    Indexes on ``(channel, message_created_at)``, ``message_created_at``,
    ``is_deleted``, and ``message_type`` support sync windows and queries.
    """

    message_id = models.BigIntegerField(unique=True, db_index=True)
    channel = models.ForeignKey(
        DiscordChannel,
        on_delete=models.CASCADE,
        related_name="messages",
        db_column="channel_id",
    )
    author = models.ForeignKey(
        DiscordProfile,
        on_delete=models.CASCADE,
        related_name="discord_messages",
        db_column="author_id",
    )
    content = models.TextField(blank=True)
    # message_type: "Default", "Reply", "GuildBoost", etc. (from DiscordChatExporter type field)
    message_type = models.CharField(max_length=50, default="Default", db_index=True)
    is_pinned = models.BooleanField(default=False, db_index=True)
    message_created_at = models.DateTimeField(db_index=True)
    message_edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    reply_to_message_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    has_attachments = models.BooleanField(default=False)
    attachment_urls = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["channel", "message_created_at"]
        indexes = [
            models.Index(fields=["channel", "message_created_at"]),
            models.Index(fields=["message_created_at"]),
            models.Index(fields=["is_deleted"]),
            models.Index(fields=["message_type"]),
        ]

    def __str__(self):
        content_preview = self.content[:50] if self.content else "(no content)"
        return f"{self.author.username}: {content_preview}"


class DiscordReaction(models.Model):
    """Aggregated emoji reaction counts on a ``DiscordMessage``.

    One row per (``message``, ``emoji``) pair (enforced by unique constraint). ``count``
    stores the total from the source payload at sync time.

    Relationships:
        ``message``: FK to ``DiscordMessage`` (column ``message_id``).
    """

    message = models.ForeignKey(
        DiscordMessage,
        on_delete=models.CASCADE,
        related_name="reactions",
        db_column="message_id",
    )
    emoji = models.CharField(max_length=255, db_index=True)
    count = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["message", "emoji"],
                name="discord_activity_tracker_msg_emoji_uniq",
            )
        ]

    def __str__(self):
        return f"{self.emoji} ({self.count})"
