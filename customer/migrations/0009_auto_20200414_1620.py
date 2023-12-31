# Generated by Django 2.2.6 on 2020-04-14 14:20

import customer.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0008_auto_20200411_1857'),
    ]

    operations = [
        migrations.AddField(
            model_name='customermatch',
            name='match_mode',
            field=models.SmallIntegerField(choices=[(0, 'Both'), (1, 'Either'), (2, 'Regexp')], default=0, help_text='Läge för prefix/suffix-match. Regexp väljs automatiskt', verbose_name='Läge'),
        ),
        migrations.AlterField(
            model_name='customermatch',
            name='prefix_match',
            field=models.CharField(blank=True, max_length=100, verbose_name='Börjar med'),
        ),
        migrations.AlterField(
            model_name='customermatch',
            name='regexp_match',
            field=models.CharField(blank=True, help_text='Används istället för prefix/suffix', max_length=250, validators=[customer.models.validate_regexp], verbose_name='Regexp'),
        ),
        migrations.AlterField(
            model_name='customermatch',
            name='suffix_match',
            field=models.CharField(blank=True, max_length=100, verbose_name='Slutar med'),
        ),
    ]
