# Generated by Django 2.2.19 on 2021-03-16 20:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0058_auto_20210316_2036'),
    ]

    operations = [
        migrations.AddField(
            model_name='leg',
            name='presence',
            field=models.BooleanField(null=True),
        ),
    ]
