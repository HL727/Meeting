# Generated by Django 2.2.19 on 2021-03-16 19:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0060_provider_software_version'),
        ('statistics', '0057_auto_20210316_1845'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='leg',
            name='meeting',
        ),
        migrations.AddField(
            model_name='call',
            name='meeting',
            field=models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to='provider.Meeting'),
        ),
        migrations.AddIndex(
            model_name='call',
            index=models.Index(condition=models.Q(meeting__isnull=False), fields=['meeting'], name='call_meeting'),
        ),
    ]
