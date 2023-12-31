# Generated by Django 2.2.25 on 2022-01-17 14:44

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0001_initial'),
        ('debuglog', '0014_auto_20211222_1823'),
    ]

    operations = [
        migrations.AddField(
            model_name='errorlog',
            name='endpoint',
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                to='endpoint.Endpoint',
            ),
        ),
        migrations.AlterField(
            model_name='errorlog',
            name='customer',
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                to='provider.Customer',
            ),
        ),
    ]
