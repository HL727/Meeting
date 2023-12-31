# Generated by Django 2.2.6 on 2019-10-24 16:38

from django.db import migrations, models


def forwards(apps, schema_editor):
    if 'postgres' not in schema_editor.connection.vendor:
        return

    schema_editor.execute(
            'UPDATE statistics_call AS c SET correlator_guid = '
            '(SELECT guid FROM statistics_callcorrelator AS cor WHERE cor.call_id = c.id LIMIT 1);'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0016_remove_target_domain'),
    ]

    operations = [
        migrations.AddField(
            model_name='call',
            name='correlator_guid',
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.RunPython(forwards, lambda x, y: x),
        migrations.DeleteModel(
            name='CallCorrelator',
        ),
    ]
