# Generated by Django 2.2.6 on 2020-04-29 17:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datastore', '0021_auto_20200423_0955'),
    ]

    operations = [
        migrations.AddField(
            model_name='conference',
            name='full_data',
            field=models.TextField(blank=True),
        ),
    ]
