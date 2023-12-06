# Generated by Django 2.2.24 on 2021-12-12 13:22

import django.contrib.postgres.indexes
from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    atomic = not settings.IS_POSTGRES

    dependencies = [
        ('statistics', '0066_leg_air_quality'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='call',
            name='statistics__guid_e1caef_idx',
        ),
        migrations.RemoveIndex(
            model_name='leg',
            name='leg_server',
        ),
        migrations.AddIndex(
            model_name='leg',
            index=models.Index(
                condition=models.Q(('guid2__isnull', False), models.Q(_negated=True, guid2='')),
                fields=['guid2', 'server'],
                name='leg_guid2',
            ),
        ),
        migrations.AddIndex(
            model_name='leg',
            index=models.Index(
                condition=models.Q(should_count_stats=True),
                fields=['server', 'tenant'],
                name='leg_server_tenant',
            ),
        ),
        *(
            [
                migrations.AddIndex(
                    model_name='leg',
                    index=django.contrib.postgres.indexes.BrinIndex(
                        fields=['ts_start', 'ts_stop'],
                        name='leg_times',
                        autosummarize=True,
                    ),
                )
            ]
            if settings.IS_POSTGRES
            else []
        ),
    ]
