# Generated by Django 2.2.24 on 2021-10-08 12:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0067_auto_20211008_1309'),
    ]

    operations = [
        migrations.AddField(
            model_name='customersettings',
            name='enable_user_debug_statistics',
            field=models.BooleanField(blank=True, default=False),
        ),
    ]
