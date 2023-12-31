# Generated by Django 2.2.6 on 2020-01-28 14:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint_provision', '0002_auto_20200128_1431'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='endpointtask',
            name='backup',
        ),
        migrations.RemoveField(
            model_name='endpointtask',
            name='commands',
        ),
        migrations.RemoveField(
            model_name='endpointtask',
            name='configuration',
        ),
        migrations.RemoveField(
            model_name='endpointtask',
            name='events',
        ),
        migrations.RemoveField(
            model_name='endpointtask',
            name='firmware_url',
        ),
        migrations.RemoveField(
            model_name='endpointtask',
            name='force_firmware',
        ),
        migrations.RemoveField(
            model_name='endpointtask',
            name='password',
        ),
        migrations.RemoveField(
            model_name='endpointtask',
            name='user',
        ),
        migrations.AlterField(
            model_name='endpointfirmware',
            name='manufacturer',
            field=models.SmallIntegerField(choices=[(10, 'CISCO_CE')]),
        ),
        migrations.AlterField(
            model_name='endpointtemplate',
            name='manufacturer',
            field=models.SmallIntegerField(choices=[(10, 'CISCO_CE')]),
        ),
    ]
