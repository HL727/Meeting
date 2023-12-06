# Generated by Django 2.2.6 on 2021-01-21 19:09

from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0050_auto_20210112_1610'),
    ]

    operations = [
        migrations.AlterField(
            model_name='provider',
            name='cluster',
            field=models.ForeignKey(blank=True, limit_choices_to={'type__in': (4, 5, 6)}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='provider.Cluster'),
        ),
        migrations.CreateModel(
            name='SettingsProfile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('target_type', models.CharField(max_length=100)),
                ('target_id', models.CharField(max_length=100, null=True)),
                ('profile_type', models.CharField(max_length=100)),
                ('profile_id', models.CharField(max_length=100)),
                ('ts_created', models.DateTimeField(auto_now_add=True)),
                ('result', jsonfield.fields.JSONField(default=dict)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='provider.SettingsProfile')),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Provider')),
            ],
            options={
                'unique_together': {('provider', 'target_type', 'target_id', 'profile_type')},
            },
        ),
        migrations.CreateModel(
            name='SettingsNode',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('settings', jsonfield.fields.JSONField(default=dict)),
                ('priority', models.SmallIntegerField(default=10)),
                ('ts_created', models.DateTimeField(auto_now_add=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.SettingsProfile')),
            ],
        ),
    ]
