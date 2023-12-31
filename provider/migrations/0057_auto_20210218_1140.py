# Generated by Django 2.2.18 on 2021-02-18 10:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0056_settingsprofile_extends_profile_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='acanocluster',
            name='clear_chat_interval',
            field=models.SmallIntegerField(null=True),
        ),
        migrations.AddField(
            model_name='acanocluster',
            name='set_call_id_as_uri',
            field=models.BooleanField(default=False),
        ),
    ]
