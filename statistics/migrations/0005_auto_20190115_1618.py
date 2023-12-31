# Generated by Django 2.1.4 on 2019-01-15 15:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0004_leg_protocol'),
    ]

    operations = [
        migrations.CreateModel(
            name='CallCorrelator',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('guid', models.CharField(db_index=True, max_length=64)),
                ('call', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='correlator', to='statistics.Call')),
            ],
        ),
        migrations.AddField(
            model_name='leg',
            name='orig_call',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='statistics.Call'),
        ),
    ]
