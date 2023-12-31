# Generated by Django 2.2.6 on 2020-08-25 08:02

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('policy_auth', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='policyauthorization',
            name='active',
        ),
        migrations.AlterField(
            model_name='policyauthorization',
            name='first_use',
            field=models.DateTimeField(editable=False, help_text='Timestamp for when this first was used by policy server', null=True),
        ),
        migrations.AlterField(
            model_name='policyauthorization',
            name='local_alias',
            field=models.CharField(db_index=True, help_text='Full alias as reported by policy server', max_length=500),
        ),
        migrations.AlterField(
            model_name='policyauthorization',
            name='settings_override',
            field=jsonfield.fields.JSONField(blank=True, default=dict, help_text='Override conference settings when using this authorization'),
        ),
    ]
