"""Discord Activity Tracker Django app.

Persists Discord guild, channel, message, and reaction data for analytics, Markdown
context export, and Pinecone indexing. All writes to app models go through
``discord_activity_tracker.services``. Ingestion is driven by management commands and
sync helpers (DiscordChatExporter and optional discord.py paths).

App config: ``discord_activity_tracker.apps.DiscordActivityTrackerConfig``.
"""
