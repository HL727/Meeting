# Generated by Django 2.2.6 on 2020-04-19 11:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0036_acanocluster'),
        ('policy', '0006_auto_20200417_1407'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='activecall',
            unique_together={('cluster', 'name')},
        ),
        migrations.AlterUniqueTogether(
            name='activeparticipant',
            unique_together={('cluster', 'guid')},
        ),
    ]
