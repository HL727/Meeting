# Generated by Django 2.2.6 on 2020-04-03 12:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('debuglog', '0008_auto_20200403_0912'),
    ]

    operations = [
        migrations.AddField(
            model_name='pexipeventlog',
            name='cluster_id',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='pexiphistorylog',
            name='cluster_id',
            field=models.IntegerField(null=True),
        ),
    ]
