# Generated by Django 2.2.18 on 2021-02-18 11:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0057_auto_20210218_1140'),
    ]

    operations = [
        migrations.AddField(
            model_name='clustersettings',
            name='remove_expired_meeting_rooms',
            field=models.IntegerField(default=240),
        ),
    ]
