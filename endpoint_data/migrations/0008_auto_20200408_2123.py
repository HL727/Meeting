# Generated by Django 2.2.6 on 2020-04-08 19:23

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint_data', '0007_auto_20200406_1334'),
    ]

    operations = [
        migrations.AlterField(
            model_name='endpointdatafile',
            name='parent',
            field=models.ForeignKey(db_constraint=False, db_index=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to='endpoint_data.EndpointDataFile'),
        ),
    ]
