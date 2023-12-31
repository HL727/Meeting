# Generated by Django 2.2.6 on 2020-08-24 17:06

import customer.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('provider', '0045_merge_20200625_1210'),
    ]

    operations = [
        migrations.CreateModel(
            name='PolicyWhitelist',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('local_alias_match', models.CharField(blank=True, help_text='Matchar från start (implicit ^)', max_length=500, validators=[customer.models.validate_regexp], verbose_name='Alias regexp-matchning')),
                ('whitelist', models.TextField(help_text='Ett inlägg per rad. Rader som börjar med { tolkas som JSON där samtliga key/values matchas', verbose_name='Lista med godkända adresser')),
                ('settings_override', jsonfield.fields.JSONField(blank=True, default=dict, help_text='Override conference attributes from this object', verbose_name='Override för rumsinställningar')),
                ('cluster', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Cluster')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Customer')),
            ],
        ),
        migrations.CreateModel(
            name='PolicyAuthorization',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('local_alias', models.CharField(db_index=True, max_length=500)),
                ('active', models.BooleanField(db_index=True, default=True)),
                ('require_fields', jsonfield.fields.JSONField(blank=True, default=dict, help_text='Matches all attributes provided to policy server against this object. E.g. {"name": "Test"}')),
                ('settings_override', jsonfield.fields.JSONField(blank=True, default=dict)),
                ('usage_limit', models.SmallIntegerField(null=True)),
                ('valid_from', models.DateTimeField(blank=True, null=True)),
                ('valid_to', models.DateTimeField()),
                ('first_use', models.DateTimeField(editable=False, null=True)),
                ('cluster', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Cluster')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Customer')),
                ('user', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'index_together': {('valid_from', 'valid_to')},
            },
        ),
    ]
