# Generated by Django 2.2.12 on 2020-05-27 19:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint_provision', '0007_endpointprovisiondata_room_controls'),
    ]

    operations = [
        migrations.AddField(
            model_name='endpointprovision',
            name='constraint',
            field=models.SmallIntegerField(blank=True, choices=[(None, 'None'), (10, 'Natt')], default=None, null=True),
        ),
        migrations.AddField(
            model_name='endpointtask',
            name='ts_schedule_attempt',
            field=models.DateTimeField(null=True),
        ),
    ]
