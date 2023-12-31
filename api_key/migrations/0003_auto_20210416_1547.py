# Generated by Django 2.2.19 on 2021-04-16 13:47

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('api_key', '0002_auto_20210416_1538'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookingapikey',
            name='ts_created',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='bookingapikey',
            name='ts_last_used',
            field=models.DateTimeField(null=True),
        ),
        migrations.AlterField(
            model_name='oauthcredential',
            name='customer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Customer'),
        ),
    ]
