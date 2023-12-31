# Generated by Django 2.2.6 on 2020-08-31 19:09

from django.db import migrations, models
import django.db.models.deletion


def initial_server_tenants(apps, schema_editor):

    Call = apps.get_model('statistics', 'Call')
    Leg = apps.get_model('statistics', 'Leg')
    Tenant = apps.get_model('statistics', 'Tenant')
    Server = apps.get_model('statistics', 'Server')
    ServerTenant = apps.get_model('statistics', 'ServerTenant')

    Tenant.objects.get_or_create(guid='')

    for tenant in Tenant.objects.all():

        for server in Server.objects.all():
            if Call.objects.filter(server=server, tenant=tenant.guid).exists():
                ServerTenant.objects.get_or_create(tenant=tenant, server=server)
                continue
            if Leg.objects.filter(server=server, tenant=tenant.guid).exists():
                ServerTenant.objects.get_or_create(tenant=tenant, server=server)
                continue


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0048_auto_20200831_2054'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServerTenant',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant', models.ForeignKey(db_index=False, on_delete=django.db.models.deletion.CASCADE, to='statistics.Tenant')),
                ('server', models.ForeignKey(db_index=False, on_delete=django.db.models.deletion.CASCADE, to='statistics.Server')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='servertenant',
            unique_together={('server', 'tenant')},
        ),
        migrations.AddField(
            model_name='tenant',
            name='servers',
            field=models.ManyToManyField(blank=True, related_name='tenants', through='statistics.ServerTenant', to='statistics.Server'),
        ),
        migrations.RunPython(initial_server_tenants, migrations.RunPython.noop),
    ]
