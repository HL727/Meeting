# Generated by Django 2.2.6 on 2020-04-20 20:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('address', '0013_auto_20200125_1040'),
    ]

    operations = [
        migrations.AddField(
            model_name='source',
            name='sync_errors',
            field=models.TextField(blank=True),
        ),
    ]
