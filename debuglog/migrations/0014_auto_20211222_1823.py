# Generated by Django 2.2.25 on 2021-12-22 17:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('debuglog', '0013_auto_20211217_1121'),
    ]

    operations = [
        migrations.AddField(
            model_name='errorlog',
            name='customer',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                to='provider.Customer',
            ),
        ),
        migrations.AlterField(
            model_name='endpointciscoprovision',
            name='endpoint',
            field=models.ForeignKey(
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                to='endpoint.Endpoint',
            ),
        ),
    ]
