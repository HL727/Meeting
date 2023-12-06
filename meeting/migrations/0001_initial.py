# Generated by Django 2.2.19 on 2021-03-25 15:53

from django.db import migrations, models
import django.db.models.deletion
import provider.models.utils
import timezone_field.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0011_update_proxy_permissions'),
        ('emailbook', '0004_auto_20210108_1436'),
        ('endpoint', '0063_auto_20210318_1326'),
        ('provider', '0061_auto_20210325_1640'),
        ('recording', '0006_recordinguseradmin_recordinguseralias'),
        ('statistics', '0060_guid_null'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=[
            migrations.CreateModel(
                name='Meeting',
                fields=[
                    ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                    ('secret_key', models.CharField(default=provider.models.utils.new_secret_key, max_length=48)),
                    ('title', models.CharField(max_length=100)),
                    ('creator', models.CharField(max_length=80)),
                    ('creator_ip', models.GenericIPAddressField(null=True, unpack_ipv4=True)),
                    ('meeting_type', models.CharField(max_length=100)),
                    ('ts_created', models.DateTimeField(auto_now_add=True)),
                    ('ts_unbooked', models.DateTimeField(editable=False, null=True)),
                    ('internal_clients', models.IntegerField(default=0)),
                    ('external_clients', models.IntegerField(null=True)),
                    ('is_internal_meeting', models.BooleanField(default=False)),
                    ('layout', models.CharField(default='allEqual', max_length=20)),
                    ('source', models.CharField(default='outlook', max_length=100)),
                    ('password', models.CharField(max_length=20)),
                    ('ts_start', models.DateTimeField()),
                    ('ts_stop', models.DateTimeField()),
                    ('timezone', timezone_field.fields.TimeZoneField(blank=True, null=True)),
                    ('is_recurring', models.BooleanField(default=False)),
                    ('recurring', models.CharField(max_length=100)),
                    ('recurring_exceptions', models.CharField(max_length=200)),
                    ('recurrence_id', models.CharField(max_length=256, null=True)),
                    ('ical_uid', models.CharField(default='', max_length=256)),
                    ('is_private', models.BooleanField(blank=True, default=False)),
                    ('room_info', models.TextField(blank=True)),
                    ('settings', models.TextField(blank=True)),
                    ('recording', models.TextField(blank=True)),
                    ('webinar', models.TextField(blank=True)),
                    ('backend_active', models.BooleanField(default=False)),
                    ('is_superseded', models.BooleanField(default=False)),
                    ('customer_confirmed', models.DateTimeField(blank=True, null=True)),
                    ('provider_ref', models.CharField(max_length=128)),
                    ('provider_ref2', models.CharField(max_length=128)),
                    ('provider_secret', models.CharField(max_length=128)),
                    ('existing_ref', models.BooleanField(blank=True, default=False)),
                    ('schedule_id', models.CharField(editable=False, max_length=20)),
                    ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Customer')),
                    ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='prev_bookings', to='meeting.Meeting')),
                    ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Provider')),
                ],
                options={
                    'db_table': 'meeting_meeting',
                },
            ),
            migrations.CreateModel(
                name='MeetingWebinar',
                fields=[
                    ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                    ('group', models.CharField(max_length=100)),
                    ('access_method_id', models.CharField(max_length=128)),
                    ('provider_ref', models.CharField(max_length=128)),
                    ('provider_secret', models.CharField(max_length=128)),
                    ('password', models.CharField(max_length=50)),
                    ('meeting', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='webinars', to='meeting.Meeting')),
                ],
                options={
                    'db_table': 'meeting_meetingwebinar',
                },
            ),
            migrations.CreateModel(
                name='MeetingDialoutEndpoint',
                fields=[
                    ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                    ('uri', models.CharField(max_length=200)),
                    ('provider_ref', models.CharField(max_length=100)),
                    ('backend_active', models.BooleanField(default=False)),
                    ('ts_activated', models.DateTimeField(null=True)),
                    ('ts_deactivated', models.DateTimeField(null=True)),
                    ('schedule_id', models.CharField(max_length=20)),
                    ('meeting', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='meeting.Meeting')),
                ],
                options={
                    'db_table': 'meeting_meetingdialoutendpoint',
                },
            ),
        ]),
    ]
