# Generated by Django 2.2.6 on 2020-03-04 13:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint_provision', '0004_endpointprovisiondata_branding_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='endpointprovisiondata',
            name='statistics',
            field=models.BooleanField(default=False),
        ),
    ]
