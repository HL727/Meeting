# Generated by Django 2.2.27 on 2022-05-18 14:31

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
            name='TraceLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    'ts_created',
                    models.DateTimeField(db_index=True, default=django.utils.timezone.localtime),
                ),
                ('content_compressed', models.BinaryField()),
                ('extra_compressed', models.BinaryField(null=True)),
                ('method', models.CharField(max_length=250)),
                ('url_base', models.CharField(max_length=250)),
                (
                    'cluster',
                    models.ForeignKey(
                        db_constraint=False,
                        db_index=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name='+',
                        to='provider.Cluster',
                    ),
                ),
                (
                    'customer',
                    models.ForeignKey(
                        db_constraint=False,
                        db_index=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name='+',
                        to='provider.Customer',
                    ),
                ),
                (
                    'endpoint',
                    models.ForeignKey(
                        db_constraint=False,
                        db_index=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name='+',
                        to='endpoint.Endpoint',
                    ),
                ),
                (
                    'provider',
                    models.ForeignKey(
                        db_constraint=False,
                        db_index=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name='+',
                        to='provider.Provider',
                    ),
                ),
            ],
            options={
                'abstract': False,
            },
            bases=(compressed_store.models.CompressedContentMixin, models.Model),
        ),
        migrations.CreateModel(
            name='ActiveTraceLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('user', models.CharField(max_length=250)),
                ('everything', models.BooleanField(default=False)),
                ('ts_start', models.DateTimeField(default=django.utils.timezone.now)),
                ('ts_stop', models.DateTimeField(null=True)),
                (
                    'ts_created',
                    models.DateTimeField(default=django.utils.timezone.now, editable=False),
                ),
                (
                    'cluster',
                    models.ForeignKey(
                        db_constraint=False,
                        db_index=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name='+',
                        to='provider.Cluster',
                    ),
                ),
                (
                    'customer',
                    models.ForeignKey(
                        db_constraint=False,
                        db_index=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name='+',
                        to='provider.Customer',
                    ),
                ),
                (
                    'endpoint',
                    models.ForeignKey(
                        db_constraint=False,
                        db_index=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name='+',
                        to='endpoint.Endpoint',
                    ),
                ),
                (
                    'provider',
                    models.ForeignKey(
                        db_constraint=False,
                        db_index=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name='+',
                        to='provider.Provider',
                    ),
                ),
            ],
        ),
    ]
