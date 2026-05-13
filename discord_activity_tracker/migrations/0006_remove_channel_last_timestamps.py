"""Remove DiscordChannel.last_synced_at and last_activity_at (use DiscordMessage instead)."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("discord_activity_tracker", "0005_channel_category_message_type_is_pinned"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="discordchannel",
            name="discord_act_last_ac_87ebfd_idx",
        ),
        migrations.RemoveField(
            model_name="discordchannel",
            name="last_activity_at",
        ),
        migrations.RemoveField(
            model_name="discordchannel",
            name="last_synced_at",
        ),
    ]
