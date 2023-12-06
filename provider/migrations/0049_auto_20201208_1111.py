# Generated by Django 2.2.6 on 2020-12-08 10:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0048_merge_20201204_1707'),
    ]

    operations = [
        migrations.AddField(
            model_name='pexipcluster',
            name='default_customer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pexip_default', to='provider.Customer'),
        ),
    ]