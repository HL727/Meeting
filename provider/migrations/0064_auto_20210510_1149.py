# Generated by Django 2.2.19 on 2021-05-10 09:49

from django.db import migrations, models
import django.db.models.deletion


def remove_duplicates(apps, schema_editor):

    PexipEndUser = apps.get_model('provider.PexipEndUser')
    PexipSpace = apps.get_model('provider.PexipSpace')

    end_users = list(PexipEndUser.objects.values_list('cluster', 'external_id', 'id', named=True))
    spaces = list(PexipEndUser.objects.values_list('cluster', 'external_id', 'id', named=True))

    existing_users = set()
    for end_user in end_users:
        cur = tuple(end_user[:2])
        if cur in existing_users:
            PexipEndUser.objects.filter(pk=end_user.id).delete()
        existing_users.add(cur)

    existing_spaces = set()
    for space in spaces:
        cur = tuple(space[:2])
        if cur in existing_spaces:
            PexipSpace.objects.filter(pk=space.id).delete()
        existing_spaces.add(cur)


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0063_delete_meeting'),
    ]

    atomic = False

    operations = [
        migrations.RunPython(remove_duplicates, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='customer',
            name='clearsea_provider',
            field=models.ForeignKey(blank=True, limit_choices_to={'type__in': (1,)}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='provider.Provider'),
        ),
        migrations.AlterField(
            model_name='customer',
            name='lifesize_provider',
            field=models.ForeignKey(blank=True, limit_choices_to={'type__in': (4, 6)}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='customers', to='provider.Cluster'),
        ),
        migrations.AlterField(
            model_name='customer',
            name='shared_key',
            field=models.CharField(default='', editable=False, max_length=40),
        ),
        migrations.AlterUniqueTogether(
            name='pexipenduser',
            unique_together={('cluster', 'external_id')},
        ),
        migrations.AlterUniqueTogether(
            name='pexipspace',
            unique_together={('cluster', 'external_id')},
        ),
    ]
