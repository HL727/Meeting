# Generated by Django 2.2.23 on 2021-06-16 10:07

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0064_auto_20210325_1653'),
    ]

    operations = [
        migrations.AddField(
            model_name='endpoint',
            name='hide_from_addressbook',
            field=models.BooleanField(blank=True, default=False),
        ),
    ]
