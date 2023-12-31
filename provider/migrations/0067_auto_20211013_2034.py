# Generated by Django 2.2.24 on 2021-10-13 18:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0066_auto_20211005_1716'),
    ]

    operations = [
        migrations.AddField(
            model_name='clustersettings',
            name='meeting_provision_mode',
            field=models.IntegerField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='clustersettings',
            name='provision_meeting_rooms_before',
            field=models.IntegerField(editable=False, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='pexipspace',
            name='is_virtual',
            field=models.BooleanField(default=False, editable=False, null=True),
        ),
    ]
