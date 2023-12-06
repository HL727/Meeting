from django.db import connection

from compressed_store.models import CompressStoreModel
from endpoint_provision.models import EndpointTask
from policy.models import PolicyLog, ExternalPolicyLog
from room_analytics.models import (
    EndpointRoomPresence,
    EndpointHeadCount,
    EndpointOldHeadCount,
    EndpointSensorValue,
)


def get_all_model_timescale_sql(check_timescale_status=False):

    target_models, errors = find_compressed_models()
    extra_models = {
        EndpointTask: 'ts_created',
        EndpointRoomPresence: 'ts',
        EndpointOldHeadCount: 'ts',
        EndpointSensorValue: 'ts',
        PolicyLog: 'ts',
        ExternalPolicyLog: 'ts',
    }

    for model, field in extra_models.items():
        cur_errors = check_related_model_errors(model)
        if cur_errors:
            errors.extend(cur_errors)
        else:
            target_models.append((model, field))

    if errors:
        raise ValueError('\n'.join(errors))

    return get_create_sql(target_models, check_timescale_status=check_timescale_status)


def get_create_sql(model_field_map, check_timescale_status=True):
    result = []
    for model, field in model_field_map:
        check_sql = '''SELECT * FROM timescaledb_information.hypertable WHERE table_schema='public' AND table_name='%s';''' % model._meta.db_table
        try:
            if check_timescale_status:
                cursor = connection.cursor()
                cursor.execute(check_sql)
                if cursor.fetchone() is None:
                    result.append('--- skipping {}'.format(model._meta.db_table))
                    continue
        except Exception as e:
            raise ValueError('Timescale not loaded. CREATE EXTENSION timescaledb;\n\n{}'.format(e))

        result.append('''ALTER TABLE %s drop CONSTRAINT %s_pkey CASCADE;''' % (model._meta.db_table, model._meta.db_table))
        result.append('''ALTER TABLE %s add primary key (id, %s);''' % (model._meta.db_table, field))
        result.append('''SELECT * FROM create_hypertable('%s', '%s',
            create_default_indexes => FALSE, if_not_exists => TRUE, migrate_data => TRUE);''' % (model._meta.db_table, field))

    return result


def find_compressed_models():
    errors = []
    result = []

    from django.apps.registry import apps
    for app in apps.all_models.values():
        for model in app.values():
            if issubclass(model, CompressStoreModel):

                cur_errors = check_related_model_errors(model)
                if cur_errors:
                    errors.extend(cur_errors)
                else:
                    result.append((model, 'ts_created'))
            else:
                cur_errors = check_forward_model_errors(model)
                if cur_errors:
                    errors.extend(cur_errors)


    return result, errors


def check_related_model_errors(model):

    errors = []

    for rel in model._meta.related_objects:
        if getattr(rel.field, 'db_constraint', False):  # TODO fix for checking m2m
            errors.append('{}.{} need db_constraint=False for timescale compatibility'.format(rel.field.model._meta.label, rel.field.name))

    return errors


def check_forward_model_errors(model):

    errors = []

    for field in model._meta.fields:
        related_model = getattr(field, 'related_model', None)
        if isinstance(related_model, str):
            continue  # invalid
        if related_model and issubclass(related_model, CompressStoreModel) and field.db_constraint:
            errors.append('{}.{} need db_constraint=False for timescale compatibility'.format(model._meta.label, field.name))

    return errors

