# Generated by Django 2.2.6 on 2020-09-18 13:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('policy_rule', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='policyrule',
            name='external_id',
            field=models.IntegerField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='policyrule',
            name='last_external_sync',
            field=models.DateTimeField(editable=False, null=True),
        ),
    ]
