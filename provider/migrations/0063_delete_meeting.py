# Generated by Django 2.2.19 on 2021-03-25 16:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0062_auto_20210325_1653'),
        ('meeting', '0001_initial'),
        ('recording', '0007_meetingrecording'),
        ('statistics', '0061_auto_20210325_1653'),
        ('endpoint', '0064_auto_20210325_1653'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=[
            migrations.DeleteModel(
                name='Meeting',
            ),
            migrations.DeleteModel(
                name='MeetingDialoutEndpoint',
            ),
            migrations.DeleteModel(
                name='MeetingRecording',
            ),
            migrations.DeleteModel(
                name='MeetingWebinar',
            ),
        ]),

    ]
