# Generated by Django 2.1.5 on 2019-06-19 13:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0007_remove_endpointstatus_customer'),
    ]

    operations = [
        migrations.AddField(
            model_name='endpointtemplate',
            name='name',
            field=models.CharField(blank=True, max_length=100, verbose_name='Namn'),
        ),
    ]
