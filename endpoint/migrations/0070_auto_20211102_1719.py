# Generated by Django 2.2.24 on 2021-11-02 16:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0069_auto_20211025_1845'),
    ]

    operations = [
        migrations.AddField(
            model_name='customersettings',
            name='ca_certificates',
            field=models.TextField(blank=True),
        ),
    ]
