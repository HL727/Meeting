# Generated by Django 2.2.6 on 2019-11-28 16:07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0019_auto_20191025_1423'),
    ]

    operations = [
        migrations.AlterField(
            model_name='domaintransform',
            name='domain',
            field=models.CharField(max_length=30, verbose_name='Domän'),
        ),
        migrations.AlterField(
            model_name='domaintransform',
            name='org_unit',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='organization.OrganizationUnit', verbose_name='Organisationsenhet'),
        ),
        migrations.AlterField(
            model_name='domaintransform',
            name='ou',
            field=models.CharField(blank=True, max_length=30, verbose_name='OU-grupp i AD'),
        ),
        migrations.AlterField(
            model_name='leg',
            name='protocol',
            field=models.SmallIntegerField(choices=[(0, 'SIP'), (1, 'H323'), (2, 'CMS'), (3, 'Lync'), (4, 'Cluster'), (5, 'Stream/recording'), (6, 'Lync SubConnection')], null=True),
        ),
        migrations.CreateModel(
            name='DomainRewrite',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alias_domain', models.CharField(max_length=200, verbose_name='Domän som ska skrivas om')),
                ('transform', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='statistics.DomainTransform')),
            ],
        ),
    ]
