# Generated by Django 2.2.6 on 2020-04-07 09:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0051_endpoint_http_mode'),
    ]

    operations = [
        migrations.AlterField(
            model_name='endpoint',
            name='mac_address',
            field=models.CharField(blank=True, db_index=True, max_length=100),
        ),
    ]
