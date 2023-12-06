# Generated by Django 2.2.6 on 2020-11-06 13:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('address', '0017_auto_20200831_1959'),
    ]

    operations = [
        migrations.AlterField(
            model_name='group',
            name='title',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='item',
            name='h323',
            field=models.CharField(blank=True, max_length=255, verbose_name='H323'),
        ),
        migrations.AlterField(
            model_name='item',
            name='sip',
            field=models.CharField(blank=True, max_length=255, verbose_name='SIP'),
        ),
        migrations.AlterField(
            model_name='item',
            name='title',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='source',
            name='title',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='tmssource',
            name='mac',
            field=models.CharField(max_length=17),
        ),
    ]
