# Generated by Django 2.2.6 on 2019-12-23 11:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0020_auto_20191128_1707'),
    ]

    operations = [
        migrations.AddField(
            model_name='server',
            name='default_domain',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
