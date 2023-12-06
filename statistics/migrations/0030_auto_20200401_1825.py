# Generated by Django 2.2.6 on 2020-04-01 16:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0029_auto_20200331_1726'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leg',
            name='local',
            field=models.CharField(max_length=300),
        ),
        migrations.AlterField(
            model_name='leg',
            name='name',
            field=models.CharField(db_index=True, max_length=300),
        ),
        migrations.AlterField(
            model_name='leg',
            name='remote',
            field=models.CharField(max_length=300),
        ),
        migrations.AlterField(
            model_name='leg',
            name='target',
            field=models.CharField(db_index=True, max_length=300),
        ),
    ]