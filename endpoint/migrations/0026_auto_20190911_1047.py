# Generated by Django 2.1.5 on 2019-09-11 08:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0025_endpointtask_backup'),
    ]

    operations = [
        migrations.AlterField(
            model_name='endpointtask',
            name='backup',
            field=models.SmallIntegerField(choices=[(1, 'Backup'), (2, 'Restore')], null=True),
        ),
    ]
