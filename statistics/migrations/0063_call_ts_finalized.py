# Generated by Django 2.2.24 on 2021-10-26 18:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0062_auto_20210601_2141'),
    ]

    operations = [
        migrations.AddField(
            model_name='call',
            name='ts_finalized',
            field=models.DateTimeField(null=True),
        ),
    ]
