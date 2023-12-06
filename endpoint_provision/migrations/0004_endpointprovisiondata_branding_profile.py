# Generated by Django 2.2.6 on 2020-01-29 19:48

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint_branding', '0002_auto_20200129_2048'),
        ('endpoint_provision', '0003_auto_20200128_1512'),
    ]

    operations = [
        migrations.AddField(
            model_name='endpointprovisiondata',
            name='branding_profile',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='endpoint_branding.EndpointBrandingProfile'),
        ),
    ]