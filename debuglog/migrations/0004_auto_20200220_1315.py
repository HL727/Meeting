# Generated by Django 2.2.6 on 2020-02-20 12:15

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('debuglog', '0003_endpointciscoprovision'),
    ]

    operations = [
        migrations.AlterField(
            model_name='acanocdrlog',
            name='ts_created',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.localtime),
        ),
        migrations.AlterField(
            model_name='acanocdrspamlog',
            name='ts_created',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.localtime),
        ),
        migrations.AlterField(
            model_name='emaillog',
            name='ts_created',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.localtime),
        ),
        migrations.AlterField(
            model_name='endpointciscoevent',
            name='ts_created',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.localtime),
        ),
        migrations.AlterField(
            model_name='endpointciscoprovision',
            name='ts_created',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.localtime),
        ),
        migrations.AlterField(
            model_name='vcscalllog',
            name='ts_created',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.localtime),
        ),
    ]
