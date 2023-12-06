# Generated by Django 2.1.5 on 2019-05-09 11:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('recording', '0005_auto_20190327_0934'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecordingUserAdmin',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_jid', models.CharField(max_length=200, verbose_name='Användarnamn administratör')),
            ],
        ),
        migrations.CreateModel(
            name='RecordingUserAlias',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('owner_jid', models.CharField(max_length=200, verbose_name='Ägare för inspelning')),
                ('admin', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='recording.RecordingUserAdmin')),
            ],
        ),
    ]
