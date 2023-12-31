# Generated by Django 2.2.19 on 2021-06-01 19:41
from django.conf import settings
from django.db import migrations, connection


class Migration(migrations.Migration):

    atomic = False  # 'sqlite' not in settings.DATABASES['default']['ENGINE']

    dependencies = [
        ('statistics', '0061_auto_20210325_1653'),
    ]

    operations = [
        migrations.RunSQL('''
            UPDATE statistics_call SET guid=NULL WHERE guid=''
        ''', migrations.RunSQL.noop),
        migrations.RunSQL('''
            delete from statistics_leg where id in (select id from statistics_leg where call_id in (select max(id) from statistics_call group by server_id, guid having count(guid) > 1))
        ''', migrations.RunSQL.noop),
        migrations.RunSQL('''
            delete from statistics_call where id in (select max(id) from statistics_call group by server_id, guid having count(guid) > 1)
        ''', migrations.RunSQL.noop),
        migrations.AlterUniqueTogether(
            name='call',
            unique_together={('guid', 'server')},
        ),
    ]
