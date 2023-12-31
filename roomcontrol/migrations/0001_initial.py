# Generated by Django 2.2.6 on 2020-02-29 16:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('provider', '0026_auto_20200222_1111'),
        ('endpoint', '0047_merge_20200204_2055'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoomControl',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=100, verbose_name='Rubrik')),
                ('prefix', models.CharField(blank=True, max_length=100, verbose_name='Prefix')),
                ('description', models.TextField(max_length=500)),
                ('ts_created', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Customer')),
            ],
        ),
        migrations.CreateModel(
            name='RoomControlFile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='roomcontrol')),
                ('control', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='roomcontrol.RoomControl')),
            ],
        ),
    ]
