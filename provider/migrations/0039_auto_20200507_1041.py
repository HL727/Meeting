# Generated by Django 2.2.6 on 2020-05-07 08:41

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('numberseries', '0002_numberrange'),
        ('provider', '0038_clusterconfig'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='ClusterConfig',
            new_name='ClusterSettings',
        ),
    ]
