# Generated by Django 2.1.5 on 2019-09-11 09:02

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0027_endpointtask_action'),
    ]

    operations = [
        migrations.AddField(
            model_name='endpointtask',
            name='endpoint_id_bak',
            field=models.IntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='endpointtask',
            name='endpoint',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='endpoint.Endpoint'),
        ),
    ]
