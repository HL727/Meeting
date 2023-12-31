# Generated by Django 2.1.5 on 2019-05-27 14:05

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0012_meetingrecording_stream_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='schedule_id',
            field=models.CharField(default='', editable=False, max_length=20),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='customer',
            name='lifesize_provider',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='customers', to='provider.Provider', verbose_name='Video-provider'),
        ),
    ]
