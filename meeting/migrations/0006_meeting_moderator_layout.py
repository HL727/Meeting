# Generated by Django 2.2.24 on 2021-12-09 15:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meeting', '0005_auto_20211013_2006'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='moderator_layout',
            field=models.CharField(default='', max_length=20),
        ),
    ]
