"""Discord ingest and export helpers (not the DB service layer).

- ``sync.chat_exporter`` — DiscordChatExporter CLI integration and JSON parsing.
- ``sync.messages`` — Normalized message batches and ``discord.py`` client helpers.
- ``sync.client`` — ``DiscordSyncClient`` wrapper.
- ``sync.exporter_window`` — DB-backed lower bounds for incremental exports.
- ``sync.export`` — Markdown export from ORM data.
"""
