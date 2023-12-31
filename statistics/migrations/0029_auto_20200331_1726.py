# Generated by Django 2.2.6 on 2020-03-31 15:26

from django.db import migrations, models
import statistics.models


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0028_auto_20200330_1854'),
    ]

    operations = [
        migrations.AlterField(
            model_name='call',
            name='cospace',
            field=models.CharField(max_length=300),
        ),
        migrations.AlterField(
            model_name='leg',
            name='protocol',
            field=models.SmallIntegerField(choices=[(0, 'SIP'), (1, 'H323'), (2, 'CMS'), (3, 'Lync'), (4, 'Cluster'), (5, 'Stream/recording'), (6, 'Lync SubConnection'), (7, 'WebRTC'), (8, 'Teams'), (9, 'GMS')], null=True),
        ),
        migrations.AlterField(
            model_name='server',
            name='secret_key',
            field=models.CharField(blank=True, default=statistics.models.new_key, editable=False, max_length=100),
        ),
        migrations.AlterField(
            model_name='server',
            name='type',
            field=models.SmallIntegerField(choices=[(0, 'Cisco Meeting Server'), (4, 'Pexip'), (1, 'Cisco VCS'), (2, 'Endpoints'), (3, 'Combine')], default=0, verbose_name='Typ'),
        ),
    ]
