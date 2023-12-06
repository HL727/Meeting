# Generated by Django 2.1.5 on 2019-04-24 12:46

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EndpointBackup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint_name', models.CharField(max_length=200)),
                ('ts_created', models.DateTimeField(auto_now_add=True)),
                ('ts_completed', models.DateTimeField(null=True)),
                ('hash', models.CharField(max_length=128)),
                ('error', models.TextField()),
                ('file', models.FileField(upload_to='backup')),
                ('endpoint', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='endpoint.Endpoint')),
            ],
        ),
        migrations.AlterField(
            model_name='endpointstatus',
            name='status',
            field=models.SmallIntegerField(choices=[(-1, 'AUTH_ERROR'), (0, 'OFFLINE'), (10, 'ONLINE'), (20, 'IN_CALL')]),
        ),
    ]
