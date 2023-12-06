# Generated by Django 2.2.24 on 2021-11-02 16:19

import django.db.models.deletion
import django.utils.timezone
import jsonfield.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0070_auto_20211102_1719'),
        ('endpoint_provision', '0018_endpointtemplate_commands'),
    ]

    operations = [
        migrations.CreateModel(
            name='EndpointProvisionedObjectHistory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    'ts_created',
                    models.DateTimeField(default=django.utils.timezone.now, editable=False),
                ),
                ('ts_replaced', models.DateTimeField(editable=False, null=True)),
                ('type', models.CharField(max_length=200)),
                ('data', jsonfield.fields.JSONField(blank=True, null=True)),
                (
                    'endpoint',
                    models.ForeignKey(
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to='endpoint.Endpoint',
                    ),
                ),
            ],
        ),
    ]
