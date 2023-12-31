# Generated by Django 2.2.6 on 2020-08-25 08:31

from django.db import migrations, models
import django.utils.timezone
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('policy_auth', '0002_auto_20200825_1002'),
    ]

    operations = [
        migrations.AddField(
            model_name='policyauthorization',
            name='created',
            field=models.DateTimeField(default=django.utils.timezone.now, editable=False),
        ),
        migrations.AddField(
            model_name='policyauthorization',
            name='source',
            field=models.CharField(blank=True, help_text='Valfritt fält för att kunna spåra vilket system som skapade en post', max_length=500, verbose_name='System'),
        ),
        migrations.AlterField(
            model_name='policyauthorization',
            name='first_use',
            field=models.DateTimeField(editable=False, help_text='Tid när den här inloggningen användes skarpt av systemet av policy-server', null=True),
        ),
        migrations.AlterField(
            model_name='policyauthorization',
            name='local_alias',
            field=models.CharField(db_index=True, help_text='Fullständigt alias, måste vara identiskt med vad som policy-server rapporterar', max_length=500),
        ),
        migrations.AlterField(
            model_name='policyauthorization',
            name='require_fields',
            field=jsonfield.fields.JSONField(blank=True, default=dict, help_text='Matchar fält från policy-server mot dessa. Ex: {"name": "Test"}'),
        ),
        migrations.AlterField(
            model_name='policyauthorization',
            name='settings_override',
            field=jsonfield.fields.JSONField(blank=True, default=dict, help_text='Ändra inställningar för videomöte som matchar denna inloggning, ex. moderator-status'),
        ),
    ]
