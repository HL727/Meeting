# Generated by Django 2.2.18 on 2021-03-07 18:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datastore', '0036_auto_20210304_1451'),
    ]

    operations = [
        migrations.AddField(
            model_name='cospace',
            name='num_access_methods',
            field=models.IntegerField(null=True),
        ),
    ]
