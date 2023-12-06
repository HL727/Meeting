# Generated by Django 2.2.24 on 2021-11-03 10:03

from django.db import migrations


def copy_states(apps, schema_editor):

    EndpointCurrentState = apps.get_model('endpoint_data', 'EndpointCurrentState')
    EndpointCurrentStateOld = apps.get_model('endpoint_data', 'EndpointCurrentStateOld')
    EndpointDataContent = apps.get_model('endpoint_data', 'EndpointDataContent')

    for state in EndpointCurrentStateOld.objects.all():

        fields = (
            'command',
            'configuration',
            'status',
            'valuespace',
        )

        kwargs = {}

        for f in fields:
            try:
                obj = getattr(state, f)
            except Exception:  # maybe removed (no db-constraint)
                continue
            if not obj:
                continue

            kwargs[f] = EndpointDataContent.objects.create(
                content_compressed=obj.content_compressed,
                extra_compressed=obj.extra_compressed,
                content_type=obj.content_type,
                ts_created=obj.ts_last_used or obj.ts_created,
            )

        EndpointCurrentState.objects.update_or_create(endpoint=state.endpoint, defaults=kwargs)


class Migration(migrations.Migration):

    dependencies = [
        ('endpoint_data', '0013_auto_20211103_1100'),
    ]

    operations = [migrations.RunPython(copy_states, migrations.RunPython.noop)]