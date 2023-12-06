# Generated by Django 2.1.5 on 2019-09-12 14:41

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0017_merge_20190903_0934'),
        ('endpoint', '0033_auto_20190912_1556'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerAutoRegisterIpNet',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('index', models.SmallIntegerField(default=0, null=True)),
                ('ip_net', models.CharField(max_length=100)),
                ('customer', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, to='provider.Customer')),
            ],
        ),
    ]
