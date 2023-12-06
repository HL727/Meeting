# Generated by Django 2.2.6 on 2020-01-23 17:05

import django.db.models.deletion
import django_extensions.db.fields.json
from django.db import migrations, models
from django.utils.timezone import now

import endpoint.consts


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('provider', '0021_vcseprovider_customer'),
        ('endpoint', '0041_auto_20200123_1503'),
    ]

    operations = [
        migrations.CreateModel(
            name='EndpointTemplate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=100, verbose_name='Namn')),
                ('manufacturer', models.SmallIntegerField(choices=[(0, 'OTHER'), (10, 'CISCO_CE'), (20, 'CISCO_CMS')])),
                ('model', models.CharField(max_length=200)),
                ('ts_created', models.DateTimeField(default=now)),
                ('settings', models.TextField()),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Customer')),
            ],
        ),
        migrations.CreateModel(
            name='EndpointTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint_id_bak', models.IntegerField(null=True)),
                ('action', models.CharField(max_length=100)),
                ('status', models.SmallIntegerField(choices=[(-10, 'ERROR'), (-1, 'CANCELLED'), (0, 'PENDING'), (10, 'COMPLETED')], default=endpoint.consts.TASKSTATUS(0))),
                ('tries', models.SmallIntegerField(default=0)),
                ('user', models.CharField(max_length=100)),
                ('configuration', django_extensions.db.fields.json.JSONField(default=dict)),
                ('commands', django_extensions.db.fields.json.JSONField(default=dict)),
                ('backup', models.SmallIntegerField(choices=[(1, 'Backup'), (2, 'Restore')], null=True)),
                ('events', models.BooleanField(default=False)),
                ('password', models.CharField(max_length=100)),
                ('firmware_url', models.CharField(max_length=300)),
                ('force_firmware', models.BooleanField(default=False)),
                ('error', models.TextField()),
                ('result', models.TextField()),
                ('ts_created', models.DateTimeField(default=now)),
                ('ts_last_attempt', models.DateTimeField(null=True)),
                ('ts_completed', models.DateTimeField(null=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Customer')),
                ('endpoint', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='endpoint.Endpoint')),
            ],
            options={
                'db_table': None,
                'ordering': ('-ts_created',),
            },
        ),
        migrations.CreateModel(
            name='EndpointFirmware',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('manufacturer', models.SmallIntegerField(choices=[(0, 'OTHER'), (10, 'CISCO_CE'), (20, 'CISCO_CMS')])),
                ('orig_file_name', models.CharField(max_length=200)),
                ('model', models.CharField(max_length=200)),
                ('version', models.CharField(max_length=200)),
                ('ts_created', models.DateTimeField(default=now)),
                ('file', models.FileField(upload_to='firmware')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Customer')),
            ],
            options={
                'db_table': None,
            },
        ),
    ]
