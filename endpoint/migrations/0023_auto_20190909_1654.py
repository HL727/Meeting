# Generated by Django 2.1.5 on 2019-09-09 14:54

from django.db import migrations, models

import endpoint.consts


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0022_endpointtask'),
    ]

    operations = [
        migrations.AddField(
            model_name='endpoint',
            name='track_ip_changes',
            field=models.BooleanField(default=False, help_text='Kräver att event-prenumeration', verbose_name='Uppdatera IP automatiskt'),
        ),
        migrations.AlterField(
            model_name='endpointtask',
            name='events',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='endpointtask',
            name='status',
            field=models.SmallIntegerField(choices=[(-10, 'ERROR'), (-1, 'CANCELLED'), (0, 'PENDING'), (10, 'COMPLETED')], default=endpoint.consts.TASKSTATUS(0)),
        ),
    ]
