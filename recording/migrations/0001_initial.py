# Generated by Django 2.1.5 on 2019-03-20 14:57

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('provider', '0007_auto_20190315_1334'),
    ]

    operations = [
        migrations.CreateModel(
            name='CoSpaceAutoStreamUrl',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider_ref', models.CharField(blank=True, max_length=128)),
                ('tenant_id', models.CharField(blank=True, max_length=128)),
                ('stream_url', models.CharField(max_length=200)),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Provider')),
            ],
        ),
    ]
