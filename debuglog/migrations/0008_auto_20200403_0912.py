# Generated by Django 2.2.6 on 2020-04-03 07:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('debuglog', '0007_pexipeventlog_uuid_start'),
    ]

    operations = [
        migrations.AddField(
            model_name='pexiphistorylog',
            name='first_start',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='pexiphistorylog',
            name='last_start',
            field=models.DateTimeField(null=True),
        ),
    ]
