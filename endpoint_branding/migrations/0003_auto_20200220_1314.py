# Generated by Django 2.2.6 on 2020-02-20 12:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint_branding', '0002_auto_20200129_2048'),
    ]

    operations = [
        migrations.AlterField(
            model_name='endpointbrandingfile',
            name='use_standard',
            field=models.BooleanField(blank=True, default=False),
        ),
    ]
