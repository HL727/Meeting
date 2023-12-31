# Generated by Django 2.2.17 on 2021-01-31 20:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0053_auto_20210131_2116'),
    ]

    operations = [
        migrations.AddField(
            model_name='provider',
            name='enabled',
            field=models.BooleanField(null=True, blank=True, default=True),
        ),
        migrations.AddField(
            model_name='provider',
            name='is_online',
            field=models.BooleanField(blank=True, null=True, default=True, editable=False),
        ),
    ]
