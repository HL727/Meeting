# Generated by Django 2.1.5 on 2019-03-26 14:17

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0009_meeting_meeting_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='streaming_provider',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='provider.VideoCenterProvider'),
        ),
        migrations.AddField(
            model_name='meetingrecording',
            name='is_separate_streaming',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AlterField(
            model_name='videocenterprovider',
            name='type',
            field=models.IntegerField(choices=[(0, 'Videocenter'), (10, 'Rec.VC'), (15, 'RTMP Streaming'), (20, 'Quickchannel'), (30, 'CMS native recording')], default=0),
        ),
    ]
