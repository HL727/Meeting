# Generated by Django 2.1.5 on 2019-09-13 17:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpointproxy', '0003_auto_20190913_1456'),
    ]

    operations = [
        migrations.AddField(
            model_name='endpointproxy',
            name='is_online',
            field=models.BooleanField(default=False),
        ),
    ]
