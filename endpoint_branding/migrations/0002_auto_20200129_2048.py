# Generated by Django 2.2.6 on 2020-01-29 19:48

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint_branding', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='endpointbrandingfile',
            name='profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='endpoint_branding.EndpointBrandingProfile'),
        ),
    ]
