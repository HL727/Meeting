# Generated by Django 2.2.6 on 2020-01-22 11:44

from django.db import migrations, models
import django.db.models.deletion
import statistics.models


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0020_auto_20200122_1242'),
        ('statistics', '0023_leg_endpoint'),
    ]

    operations = [
        migrations.AddField(
            model_name='server',
            name='customer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='provider.Customer'),
        ),
        migrations.AddField(
            model_name='server',
            name='secret_key',
            field=models.CharField(default='', max_length=100),
        ),
        migrations.AlterField(
            model_name='server',
            name='secret_key',
            field=models.CharField(default=statistics.models.new_key, max_length=100),
        ),
        migrations.AddField(
            model_name='server',
            name='type',
            field=models.SmallIntegerField(choices=[(0, 'Cisco Meeting Server'), (1, 'Cisco VCS'), (2, 'Endpoints')], default=0),
        ),
    ]
