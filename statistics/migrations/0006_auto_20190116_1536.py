# Generated by Django 2.1.4 on 2019-01-16 14:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0005_auto_20190115_1618'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leg',
            name='protocol',
            field=models.SmallIntegerField(choices=[(0, 'SIP'), (1, 'H323'), (2, 'CMS'), (3, 'Lync'), (4, 'Cluster')], null=True),
        ),
    ]
