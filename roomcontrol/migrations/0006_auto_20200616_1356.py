# Generated by Django 2.2.6 on 2020-06-16 11:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('roomcontrol', '0005_roomcontroltemplate'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='roomcontrolfile',
            name='file',
        ),
        migrations.RemoveField(
            model_name='roomcontrolfile',
            name='orig_file_name',
        ),
        migrations.AddField(
            model_name='roomcontrolfile',
            name='content',
            field=models.TextField(default=''),
        ),
    ]
