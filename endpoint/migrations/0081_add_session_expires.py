# Generated by Django 2.2.27 on 2022-06-20 07:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0080_auto_20211208_0909'),
    ]

    operations = [
        migrations.AddField(
            model_name='endpoint',
            name='session_expires',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]
