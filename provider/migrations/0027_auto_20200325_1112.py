# Generated by Django 2.2.6 on 2020-03-25 10:12

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0026_auto_20200222_1111'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProviderLoad',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ts_created', models.DateTimeField(default=django.utils.timezone.now)),
                ('load', models.IntegerField()),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Provider')),
            ],
        ),
    ]
