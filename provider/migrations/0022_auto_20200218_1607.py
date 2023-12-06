# Generated by Django 2.2.6 on 2020-02-18 15:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0021_vcseprovider_customer'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='enable_core',
            field=models.BooleanField(default=True, editable=False, verbose_name='Aktivera åtkomst till Core'),
        ),
        migrations.AddField(
            model_name='customer',
            name='enable_epm',
            field=models.BooleanField(default=True, editable=False, verbose_name='Aktivera åtkomst till EPM'),
        ),
    ]