# Merge parallel branches from 0004: WG21 author_alias vs YouTube speaker chain.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("cppa_user_tracker", "0005_wg21paperauthorprofile_author_alias"),
        ("cppa_user_tracker", "0007_youtubespeaker_external_id"),
    ]

    operations = []
