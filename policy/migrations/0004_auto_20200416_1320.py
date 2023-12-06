# Generated by Django 2.2.6 on 2020-04-16 11:20

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0036_acanocluster'),
        ('policy', '0003_auto_20200414_1624'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customerpolicy',
            name='participant_limit',
            field=models.PositiveIntegerField(blank=True, editable=False, null=True, verbose_name='Total'),
        ),
        migrations.CreateModel(
            name='ActiveParticipant',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ts_created', models.DateTimeField(default=django.utils.timezone.now)),
                ('guid', models.CharField(max_length=100)),
                ('name', models.CharField(max_length=100)),
                ('is_gateway', models.BooleanField(default=False)),
                ('cluster', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='provider.Cluster')),
                ('customer', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='provider.Customer')),
            ],
            options={
                'unique_together': {('cluster', 'customer', 'guid')},
            },
        ),
        migrations.CreateModel(
            name='ActiveCall',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ts_created', models.DateTimeField(default=django.utils.timezone.now)),
                ('name', models.CharField(max_length=100)),
                ('cluster', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='provider.Cluster')),
                ('customer', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='provider.Customer')),
            ],
            options={
                'unique_together': {('cluster', 'customer', 'name')},
            },
        ),
    ]