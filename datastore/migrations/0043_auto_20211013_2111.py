# Generated by Django 2.2.24 on 2021-10-13 19:11

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0067_auto_20211013_2034'),
        ('datastore', '0042_auto_20210510_1140'),
    ]

    operations = [
        migrations.AddField(
            model_name='conference',
            name='guid',
            field=models.UUIDField(default=None, null=True, editable=False, blank=True),
        ),
        migrations.AddField(
            model_name='conference',
            name='is_virtual',
            field=models.BooleanField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='conference',
            name='is_scheduled',
            field=models.BooleanField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='conferencealias',
            name='guid',
            field=models.UUIDField(blank=True, default=None, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='conferencealias',
            name='is_virtual',
            field=models.BooleanField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='conferenceautoparticipant',
            name='guid',
            field=models.UUIDField(blank=True, default=None, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='conferenceautoparticipant',
            name='is_virtual',
            field=models.BooleanField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name='conference',
            name='guid',
            field=models.UUIDField(blank=True, default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name='conferencealias',
            name='guid',
            field=models.UUIDField(blank=True, default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name='conferenceautoparticipant',
            name='guid',
            field=models.UUIDField(blank=True, default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='cospace',
            name='is_scheduled',
            field=models.BooleanField(null=True),
        ),
        migrations.AlterUniqueTogether(
            name='cospace',
            unique_together={('cid', 'provider')},
        ),
        migrations.AlterUniqueTogether(
            name='cospaceaccessmethod',
            unique_together={('aid', 'provider')},
        ),
        migrations.AlterUniqueTogether(
            name='user',
            unique_together={('uid', 'provider')},
        ),
        migrations.AlterUniqueTogether(
            name='conference',
            unique_together={('guid', 'provider'), ('cid', 'provider')},
        ),
        migrations.AlterUniqueTogether(
            name='conferencealias',
            unique_together={('aid', 'provider'), ('guid', 'provider')},
        ),
        migrations.AlterUniqueTogether(
            name='conferenceautoparticipant',
            unique_together={('pid', 'provider'), ('guid', 'provider')},
        ),
    ]
