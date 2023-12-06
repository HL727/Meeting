# Generated by Django 2.2.27 on 2022-04-12 14:55

import compressed_store.models
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('debuglog', '0015_errorlog_endpoint'),
    ]

    operations = [
        migrations.CreateModel(
            name='EndpointPolyProvision',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    'ts_created',
                    models.DateTimeField(db_index=True, default=django.utils.timezone.localtime),
                ),
                ('content_compressed', models.BinaryField()),
                ('extra_compressed', models.BinaryField(null=True)),
                ('ip', models.GenericIPAddressField(null=True)),
                ('event', models.CharField(max_length=100)),
                (
                    'endpoint',
                    models.ForeignKey(
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to='endpoint.Endpoint',
                    ),
                ),
            ],
            options={
                'abstract': False,
            },
            bases=(compressed_store.models.CompressedContentMixin, models.Model),
        ),
    ]
