# Generated by Django 2.1.5 on 2019-08-23 14:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0016_tandbergprovider_phonebook_url'),
        ('address', '0005_source_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='VCSSource',
            fields=[
                ('source_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='address.Source')),
                ('limit_domains', models.CharField(max_length=300)),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.VCSEProvider')),
            ],
            bases=('address.source',),
        ),
        migrations.RemoveField(
            model_name='cmscospacesource',
            name='last_sync',
        ),
        migrations.RemoveField(
            model_name='cmscospacesource',
            name='prefix',
        ),
        migrations.RemoveField(
            model_name='cmsusersource',
            name='last_sync',
        ),
        migrations.RemoveField(
            model_name='cmsusersource',
            name='prefix',
        ),
        migrations.RemoveField(
            model_name='epmsource',
            name='prefix',
        ),
        migrations.RemoveField(
            model_name='manualsource',
            name='prefix',
        ),
        migrations.RemoveField(
            model_name='tmssource',
            name='prefix',
        ),
        migrations.AddField(
            model_name='source',
            name='last_sync',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='source',
            name='prefix',
            field=models.CharField(default='Undefined', max_length=200),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='source',
            name='address_book',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sources', to='address.AddressBook'),
        ),
    ]