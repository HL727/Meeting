# Generated by Django 2.1.5 on 2019-03-27 07:37

from django.db import migrations, models
import recording.models


class Migration(migrations.Migration):

    dependencies = [
        ('recording', '0003_auto_20190326_1555'),
    ]

    operations = [
        migrations.AddField(
            model_name='acanorecording',
            name='secret_key',
            field=models.CharField(db_index=True, default=recording.models.get_secret, max_length=64),
        ),
    ]
