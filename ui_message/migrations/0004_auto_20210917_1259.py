from collections import Counter


from django.db import migrations


def fix_duplicates(apps, schema_editor):

    Message = apps.get_model('ui_message.Message')
    counter = Counter(Message.objects.order_by('-active', 'id').values_list('customer', 'type'))

    for k, v in counter.items():
        if k[0] and v > 1:
            for m in Message.objects.filter(customer=k[0], type=k[1])[1:]:
                m.delete()


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('provider', '0065_add_dial_out_location_and_ivr_branding'),
        ('ui_message', '0003_auto_20191126_1308'),
    ]

    operations = [
        migrations.RunPython(fix_duplicates, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='message',
            unique_together={('customer', 'type')},
        ),
    ]
