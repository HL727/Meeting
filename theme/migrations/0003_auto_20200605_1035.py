# Generated by Django 2.2.6 on 2020-06-05 08:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('theme', '0002_theme_dark_mode'),
    ]

    operations = [
        migrations.AlterField(
            model_name='theme',
            name='dark_mode',
            field=models.BooleanField(default=True, verbose_name='Använd mörk bakgrund där logotyp visas'),
        ),
    ]
