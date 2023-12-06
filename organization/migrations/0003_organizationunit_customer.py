# Generated by Django 2.1.5 on 2019-08-26 14:08

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0016_tandbergprovider_phonebook_url'),
        ('organization', '0002_auto_20190110_1434'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizationunit',
            name='customer',
            field=models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to='provider.Customer'),
        ),
    ]
