# Generated by Django 2.2.27 on 2022-04-23 15:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0067_index_fix'),
    ]

    operations = [
        migrations.RunSQL(
            r'''UPDATE statistics_leg SET should_count_stats='t'
            WHERE duration >= 120 AND should_count_stats = 'f' AND guid <> '' AND server_id IN (
                SELECT id FROM statistics_server WHERE type=2
            )
        ''',
            migrations.RunSQL.noop,
        )
    ]