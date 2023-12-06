# Generated by Django 2.1.5 on 2019-06-20 09:05

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0015_auto_20190620_1105'),
        ('endpoint', '0008_endpointtemplate_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='EndpointMeetingParticipant',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.AddField(
            model_name='endpoint',
            name='email_key',
            field=models.CharField(blank=True, max_length=200, verbose_name='E-postbrevlåda'),
        ),
        migrations.AddField(
            model_name='endpointmeetingparticipant',
            name='endpoint',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meetings', to='endpoint.Endpoint'),
        ),
        migrations.AddField(
            model_name='endpointmeetingparticipant',
            name='meeting',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='endpoints', to='provider.Meeting'),
        ),
    ]
