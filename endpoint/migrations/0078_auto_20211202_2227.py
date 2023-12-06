# Generated by Django 2.2.24 on 2021-12-02 21:27

from django.db import migrations, models

import endpoint.models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0077_auto_20211129_1229'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customersettings',
            name='proxy_password',
            field=models.CharField(
                default=endpoint.models.new_proxy_secret, max_length=100, null=True, unique=True
            ),
        ),
    ]
