# Generated by Django 2.1.5 on 2019-06-19 11:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint', '0004_auto_20190424_1610'),
    ]

    operations = [
        migrations.CreateModel(
            name='EndpointTemplate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('manufacturer', models.SmallIntegerField(choices=[(0, 'OTHER'), (10, 'CISCO_CE'), (20, 'CISCO_CMS')])),
                ('model', models.CharField(max_length=200)),
                ('ts_created', models.DateTimeField(auto_now_add=True)),
                ('settings', models.TextField()),
            ],
        ),
    ]
