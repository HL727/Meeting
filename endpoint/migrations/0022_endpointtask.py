# Generated by Django 2.1.5 on 2019-09-09 09:52

import django.db.models.deletion
import django_extensions.db.fields.json
from django.db import migrations, models

import endpoint.consts


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0021_endpointbackup_slug'),
    ]

    operations = [
        migrations.CreateModel(
            name='EndpointTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.SmallIntegerField(choices=[(-1, 'CANCELLED'), (0, 'PENDING'), (10, 'COMPLETED')], default=endpoint.consts.TASKSTATUS(0))),
                ('tries', models.SmallIntegerField(default=0)),
                ('user', models.CharField(max_length=100)),
                ('configuration', django_extensions.db.fields.json.JSONField(default=dict)),
                ('commands', django_extensions.db.fields.json.JSONField(default=dict)),
                ('events', models.BooleanField()),
                ('password', models.CharField(max_length=100)),
                ('firmware_url', models.CharField(max_length=300)),
                ('error', models.TextField()),
                ('result', models.TextField()),
                ('ts_created', models.DateTimeField(auto_now_add=True)),
                ('ts_last_attempt', models.DateTimeField(auto_now_add=True)),
                ('ts_completed', models.DateTimeField(null=True)),
                ('endpoint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='endpoint.Endpoint')),
            ],
        ),
    ]
