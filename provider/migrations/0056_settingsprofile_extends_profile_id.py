# Generated by Django 2.2.18 on 2021-02-16 12:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0055_auto_20210209_1342'),
    ]

    operations = [
        migrations.AddField(
            model_name='settingsprofile',
            name='extends_profile_id',
            field=models.CharField(max_length=100, null=True),
        ),
    ]
