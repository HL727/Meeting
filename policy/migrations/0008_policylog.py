# Generated by Django 2.2.6 on 2020-04-20 12:57

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0036_acanocluster'),
        ('policy', '0007_auto_20200419_1323'),
    ]

    operations = [
        migrations.CreateModel(
            name='PolicyLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ts', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('message', models.TextField()),
                ('guid', models.CharField(max_length=500)),
                ('level', models.SmallIntegerField(choices=[(1, 'Debug'), (2, 'Warning')], default=1)),
                ('type', models.SmallIntegerField(choices=[(0, 'Unknown'), (1, 'Participant'), (2, 'Call')])),
                ('customer', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='provider.Customer')),
            ],
        ),
    ]
