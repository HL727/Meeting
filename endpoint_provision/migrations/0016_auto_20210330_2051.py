# Generated by Django 2.2.19 on 2021-03-30 18:51

import django.utils.timezone
from django.db import migrations, models


def migrate_time(apps, schema_editor):

    apps.get_model('endpoint_provision', 'EndpointTask').objects.update(ts_last_change=models.F('ts_created'))


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('endpoint_provision', '0015_auto_20210330_2048'),
    ]

    operations = [
        migrations.AlterField(
            model_name='endpointtask',
            name='ts_last_change',
            field=models.DateTimeField(default=django.utils.timezone.now, null=True),
        ),
        migrations.RunPython(migrate_time, migrations.RunPython.noop),
    ]