# Generated by Django 2.2.6 on 2020-08-24 17:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0010_auto_20200515_1634'),
    ]

    operations = [
        migrations.AddField(
            model_name='customermatch',
            name='require_authorization',
            field=models.BooleanField(default=False, help_text='Fungerar endast om policyserver är aktiverad', verbose_name='Kräv extern autentisering'),
        ),
    ]