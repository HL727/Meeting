# Generated by Django 2.2.24 on 2021-12-07 17:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0065_reset_old_calls'),
    ]

    operations = [
        migrations.AddField(
            model_name='leg',
            name='air_quality',
            field=models.SmallIntegerField(null=True),
        ),
    ]
