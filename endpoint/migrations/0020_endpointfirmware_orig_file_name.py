# Generated by Django 2.1.5 on 2019-09-09 08:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0019_auto_20190906_1539'),
    ]

    operations = [
        migrations.AddField(
            model_name='endpointfirmware',
            name='orig_file_name',
            field=models.CharField(default='', max_length=200),
            preserve_default=False,
        ),
    ]
