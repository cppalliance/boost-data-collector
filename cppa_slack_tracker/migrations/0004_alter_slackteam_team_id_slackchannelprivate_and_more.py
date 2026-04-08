# Slack private schema, SlackChannelPrivate, SlackMessagePrivate, and PostgreSQL grants.

from __future__ import annotations

import logging
import re

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

logger = logging.getLogger(__name__)

_PG_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SCHEMA = "slack_private"
_TABLES = (
    "cppa_slack_tracker_slackchannel_private",
    "cppa_slack_tracker_slackmessage_private",
)


def _validate_pg_role(name: str) -> str:
    if not _PG_IDENT.fullmatch(name):
        raise ValueError(
            "PRIVATE_ACCESS_USER must be a valid PostgreSQL identifier "
            f"(letters, digits, underscore; letter or underscore first): {name!r}"
        )
    return name


def _pg_qualified_ident(connection, schema: str, name: str) -> str:
    """Match Django db_table hack: schema + '.' + relation -> \"schema\".\"name\"."""
    return connection.ops.quote_name(f'{schema}"."{name}')


def _flush_deferred_ddl(schema_editor) -> None:
    """Run deferred SQL now so tables exist before REVOKE/GRANT in RunPython."""
    while schema_editor.deferred_sql:
        schema_editor.execute(schema_editor.deferred_sql.pop(0))


def apply_slack_private_schema(_apps, schema_editor) -> None:
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        logger.info("Not PostgreSQL; skipping CREATE SCHEMA slack_private.")
        return
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")
        cursor.execute(f"REVOKE ALL ON SCHEMA {_SCHEMA} FROM PUBLIC")


def reverse_slack_private_schema(_apps, schema_editor) -> None:
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")


def apply_private_table_grants(_apps, schema_editor) -> None:
    role = getattr(settings, "PRIVATE_ACCESS_USER", None) or ""
    role = role.strip()
    if not role:
        logger.warning(
            "PRIVATE_ACCESS_USER is unset; skipping private Slack table GRANT/REVOKE "
            "(set env and re-run migrate if needed)."
        )
        return

    role = _validate_pg_role(role)
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        logger.info("Not PostgreSQL; skipping private Slack table GRANT/REVOKE.")
        return

    _flush_deferred_ddl(schema_editor)

    with connection.cursor() as cursor:
        cursor.execute(
            f"GRANT USAGE ON SCHEMA {connection.ops.quote_name(_SCHEMA)} TO {role}"
        )
        for table in _TABLES:
            qtable = _pg_qualified_ident(connection, _SCHEMA, table)
            cursor.execute(f"REVOKE ALL ON TABLE {qtable} FROM PUBLIC")
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER "
                f"ON TABLE {qtable} TO {role}"
            )
            qseq = _pg_qualified_ident(connection, _SCHEMA, f"{table}_id_seq")
            cursor.execute(f"REVOKE ALL ON SEQUENCE {qseq} FROM PUBLIC")
            cursor.execute(f"GRANT USAGE, SELECT ON SEQUENCE {qseq} TO {role}")


def reverse_private_table_grants(_apps, schema_editor) -> None:
    role = getattr(settings, "PRIVATE_ACCESS_USER", None) or ""
    role = role.strip()
    if not role or not _PG_IDENT.fullmatch(role):
        return
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        for table in _TABLES:
            qtable = _pg_qualified_ident(connection, _SCHEMA, table)
            cursor.execute(
                f"REVOKE ALL PRIVILEGES ON TABLE {qtable} FROM {role} CASCADE"
            )
            qseq = _pg_qualified_ident(connection, _SCHEMA, f"{table}_id_seq")
            cursor.execute(
                f"REVOKE ALL PRIVILEGES ON SEQUENCE {qseq} FROM {role} CASCADE"
            )
        cursor.execute(
            f"REVOKE USAGE ON SCHEMA {connection.ops.quote_name(_SCHEMA)} FROM {role}"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("cppa_user_tracker", "0004_alter_slackuser_slack_user_id_and_more"),
        ("cppa_slack_tracker", "0003_alter_slackchannel_unique_team_channel_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="slackteam",
            name="team_id",
            field=models.CharField(max_length=50, unique=True),
        ),
        migrations.RunPython(apply_slack_private_schema, reverse_slack_private_schema),
        migrations.CreateModel(
            name="SlackChannelPrivate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("channel_id", models.CharField(db_index=True, max_length=50)),
                ("channel_name", models.CharField(db_index=True, max_length=255)),
                (
                    "channel_type",
                    models.CharField(
                        choices=[
                            ("private_channel", "Private channel"),
                            ("mpim", "Multi-party direct message"),
                            ("im", "Direct message"),
                        ],
                        db_index=True,
                        help_text="Type: private_channel, mpim, or im (not public_channel).",
                        max_length=50,
                    ),
                ),
                ("description", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "creator",
                    models.ForeignKey(
                        blank=True,
                        db_column="creator_user_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_private_channels",
                        to="cppa_user_tracker.slackuser",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        db_column="team_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="private_channels",
                        to="cppa_slack_tracker.slackteam",
                    ),
                ),
            ],
            options={
                "verbose_name": "Slack Channel (non-public)",
                "verbose_name_plural": "Slack Channels (non-public)",
                "db_table": 'slack_private"."cppa_slack_tracker_slackchannel_private',
            },
        ),
        migrations.AddConstraint(
            model_name="slackchannelprivate",
            constraint=models.UniqueConstraint(
                fields=("team", "channel_id"),
                name="unique_team_channel_id_private",
            ),
        ),
        migrations.CreateModel(
            name="SlackMessagePrivate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "ts",
                    models.CharField(
                        db_index=True,
                        help_text="Slack message timestamp (unique per channel)",
                        max_length=50,
                    ),
                ),
                ("message", models.TextField(blank=True)),
                (
                    "thread_ts",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Thread timestamp if this is a threaded message",
                        max_length=50,
                        null=True,
                    ),
                ),
                ("slack_message_created_at", models.DateTimeField(db_index=True)),
                (
                    "slack_message_updated_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "channel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="cppa_slack_tracker.slackchannelprivate",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        db_column="slack_user_id",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="private_slack_messages",
                        to="cppa_user_tracker.slackuser",
                    ),
                ),
            ],
            options={
                "verbose_name": "Slack Message (non-public channel)",
                "verbose_name_plural": "Slack Messages (non-public channels)",
                "db_table": 'slack_private"."cppa_slack_tracker_slackmessage_private',
                "unique_together": {("channel", "ts")},
            },
        ),
        migrations.RunPython(apply_private_table_grants, reverse_private_table_grants),
    ]
