# Generated by Django 2.2.19 on 2021-03-31 12:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('calendar_invite', '0002_auto_20210325_1707'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendar',
            name='ts_last_sync',
            field=models.DateTimeField(editable=False, null=True),
        ),
    ]
