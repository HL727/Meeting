# Generated by Django 2.2.12 on 2020-06-26 13:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint_provision', '0008_auto_20200626_1406'),
    ]

    operations = [
        migrations.AddField(
            model_name='endpointprovisiondata',
            name='clear_room_controls',
            field=models.BooleanField(default=False, null=True),
        ),
    ]
