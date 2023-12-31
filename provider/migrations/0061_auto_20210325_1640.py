# Generated by Django 2.2.19 on 2021-03-25 15:40

from django.db import migrations, models
import timezone_field.fields


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0060_provider_software_version'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='ical_uid',
            field=models.CharField(default='', max_length=256),
        ),
        migrations.AddField(
            model_name='meeting',
            name='recurrence_id',
            field=models.CharField(max_length=256, null=True),
        ),
        migrations.AddField(
            model_name='meeting',
            name='timezone',
            field=timezone_field.fields.TimeZoneField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='meeting',
            name='creator_ip',
            field=models.GenericIPAddressField(null=True, unpack_ipv4=True),
        ),
    ]
