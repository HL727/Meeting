# Generated by Django 2.1.5 on 2019-09-10 13:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0023_auto_20190909_1654'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='endpoint',
            name='has_warnings',
        ),
        migrations.AddField(
            model_name='endpointstatus',
            name='has_warnings',
            field=models.BooleanField(default=False),
        ),
    ]
