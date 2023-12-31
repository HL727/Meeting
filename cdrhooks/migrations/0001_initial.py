# Generated by Django 2.1.4 on 2018-12-06 13:45

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('provider', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='Dialout',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dialstring', models.CharField(max_length=100, verbose_name='Uppringningsadress')),
                ('persistant', models.BooleanField(default=False, verbose_name='Håller samtalet öppet')),
                ('ts_created', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='Hook',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider_ref', models.CharField(max_length=200, verbose_name='Cospace')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktiv')),
                ('recording_key', models.CharField(max_length=200)),
                ('last_session_start', models.DateTimeField(null=True)),
                ('last_session_end', models.DateTimeField(null=True)),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='provider.Customer', verbose_name='Kund')),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Provider')),
            ],
        ),
        migrations.CreateModel(
            name='ScheduledDialout',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider_ref', models.CharField(max_length=200, verbose_name='Cospace')),
                ('provider_ref2', models.CharField(blank=True, max_length=200, verbose_name='Call ID')),
                ('ts_start', models.DateTimeField()),
                ('ts_stop', models.DateTimeField(null=True)),
                ('task_index', models.SmallIntegerField(default=0, verbose_name='Active celery task id')),
                ('is_active', models.BooleanField(default=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Customer')),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Provider')),
            ],
        ),
        migrations.CreateModel(
            name='ScheduledDialoutPart',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dialstring', models.CharField(max_length=100)),
                ('redial', models.BooleanField(default=True)),
                ('backend_active', models.BooleanField(default=False)),
                ('ts_last_check', models.DateTimeField(default=None, null=True)),
                ('dial_count', models.SmallIntegerField(default=0)),
                ('provider_ref', models.CharField(editable=False, max_length=200, verbose_name='Participant id')),
                ('dialout', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parts', to='cdrhooks.ScheduledDialout')),
            ],
        ),
        migrations.CreateModel(
            name='Session',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider_ref', models.CharField(max_length=200, verbose_name='Call')),
                ('recording_ref', models.CharField(max_length=100)),
                ('refs_json', models.TextField(blank=True)),
                ('ts_start', models.DateTimeField(auto_now_add=True, null=True)),
                ('ts_stop', models.DateTimeField(null=True)),
                ('ts_last_active', models.DateTimeField(null=True)),
                ('backend_active', models.BooleanField(default=False)),
                ('hook', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cdrhooks.Hook')),
            ],
        ),
        migrations.AddField(
            model_name='dialout',
            name='hook',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cdrhooks.Hook'),
        ),
    ]
