# Generated by Django 2.2.6 on 2020-04-17 10:19

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('debuglog', '0009_auto_20200403_1436'),
        ('statistics', '0041_auto_20200417_1126'),
    ]

    operations = [
        migrations.AddField(
            model_name='call',
            name='cdr_log',
            field=models.ForeignKey(db_constraint=False, db_index=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='debuglog.PexipEventLog'),
        ),
        migrations.AddField(
            model_name='call',
            name='history_log',
            field=models.ForeignKey(db_constraint=False, db_index=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='debuglog.PexipHistoryLog'),
        ),
        migrations.AddField(
            model_name='leg',
            name='cdr_log',
            field=models.ForeignKey(db_constraint=False, db_index=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='debuglog.PexipEventLog'),
        ),
        migrations.AddField(
            model_name='leg',
            name='history_log',
            field=models.ForeignKey(db_constraint=False, db_index=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='debuglog.PexipHistoryLog'),
        ),
    ]
