# Generated by Django 2.1.5 on 2019-05-29 14:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datastore', '0004_auto_20190517_1031'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='ts_instruction_email_sent',
            field=models.DateTimeField(null=True),
        ),
    ]