# Generated by Django 2.2.6 on 2020-03-25 10:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0027_auto_20200325_1112'),
    ]

    operations = [
        migrations.AddField(
            model_name='providerload',
            name='participant_count',
            field=models.IntegerField(default=0),
        ),
    ]