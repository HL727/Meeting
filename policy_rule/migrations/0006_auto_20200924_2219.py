# Generated by Django 2.2.6 on 2020-09-24 20:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('policy_rule', '0005_auto_20200924_2151'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='policyrule',
            options={'ordering': ('priority',)},
        ),
        migrations.AlterUniqueTogether(
            name='policyrule',
            unique_together={('cluster', 'external_id')},
        ),
    ]