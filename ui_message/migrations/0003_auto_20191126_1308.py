# Generated by Django 2.2.6 on 2019-11-26 12:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_message', '0002_auto_20190208_1032'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='extend_other',
            field=models.IntegerField(blank=True, null=True, choices=[]),
        ),
    ]
