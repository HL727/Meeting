# Generated by Django 2.1.5 on 2019-09-04 13:10

import address.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('address', '0011_auto_20190904_1508'),
    ]

    operations = [
        migrations.AlterField(
            model_name='addressbook',
            name='secret_key',
            field=models.CharField(default=address.models.new_key, max_length=64, unique=True),
        ),
    ]
