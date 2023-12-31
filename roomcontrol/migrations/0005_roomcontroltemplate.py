# Generated by Django 2.2.6 on 2020-05-19 09:08

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('roomcontrol', '0004_roomcontrolfile_orig_file_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoomControlTemplate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=100, verbose_name='Rubrik')),
                ('description', models.TextField(blank=True, max_length=500)),
                ('ts_created', models.DateTimeField(auto_now_add=True)),
                ('controls', models.ManyToManyField(blank=True, related_name='templates', to='roomcontrol.RoomControl')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Customer')),
            ],
        ),
    ]
