# Generated by Django 2.2.27 on 2022-05-24 15:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0068_fix_endpoint_event_calls'),
    ]

    operations = [
        migrations.AddField(
            model_name='call',
            name='should_count_stats',
            field=models.BooleanField(null=True),
        ),
    ]
