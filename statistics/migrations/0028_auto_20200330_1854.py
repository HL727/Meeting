# Generated by Django 2.2.6 on 2020-03-30 16:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0031_auto_20200330_1720'),
        ('statistics', '0027_auto_20200228_2015'),
    ]

    operations = [
        migrations.AddField(
            model_name='server',
            name='cluster',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='provider.Cluster'),
        ),
    ]
