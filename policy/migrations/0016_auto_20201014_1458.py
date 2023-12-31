# Generated by Django 2.2.6 on 2020-10-14 12:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('policy', '0015_auto_20201014_1457'),
    ]

    operations = [
        migrations.AddField(
            model_name='clusterpolicy',
            name='enable_gateway_rules',
            field=models.BooleanField(blank=True, default=False),
        ),
        migrations.AlterField(
            model_name='clusterpolicy',
            name='hard_limit_action',
            field=models.SmallIntegerField(choices=[(0, 'Ignore'), (5, 'Log'), (30, 'Lower quality to SD'), (35, 'Lower quality to 720p'), (100, 'Reject')], default=0),
        ),
        migrations.AlterField(
            model_name='clusterpolicy',
            name='soft_limit_action',
            field=models.SmallIntegerField(choices=[(0, 'Ignore'), (5, 'Log'), (30, 'Lower quality to SD'), (35, 'Lower quality to 720p'), (100, 'Reject')], default=0),
        ),
        migrations.AlterField(
            model_name='customerpolicy',
            name='hard_limit_action',
            field=models.SmallIntegerField(choices=[(-1, 'Standardvärde'), (0, 'Ignore'), (5, 'Log'), (100, 'Reject')], default=-1),
        ),
        migrations.AlterField(
            model_name='customerpolicy',
            name='soft_limit_action',
            field=models.SmallIntegerField(choices=[(-1, 'Standardvärde'), (0, 'Ignore'), (5, 'Log'), (100, 'Reject')], default=-1),
        ),
        migrations.AlterField(
            model_name='externalpolicylog',
            name='action',
            field=models.SmallIntegerField(choices=[(0, 'Ignore'), (5, 'Log'), (30, 'Lower quality to SD'), (35, 'Lower quality to 720p'), (100, 'Reject')], default=0),
        ),
    ]
