# Generated by Django 2.2.6 on 2020-11-18 13:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('policy_auth', '0007_auto_20200827_1216'),
    ]

    operations = [
        migrations.AddField(
            model_name='policyauthorizationoverride',
            name='match_location_name',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Matcha endast samtal i denna location'),
        ),
        migrations.AddField(
            model_name='policyauthorizationoverride',
            name='match_incoming_h323',
            field=models.BooleanField(blank=True, default=True, verbose_name='Matcha inkommande H323'),
        ),
        migrations.AddField(
            model_name='policyauthorizationoverride',
            name='match_incoming_sip',
            field=models.BooleanField(blank=True, default=True, verbose_name='Matcha inkommande SIP-samtal'),
        ),
        migrations.AddField(
            model_name='policyauthorizationoverride',
            name='match_incoming_skype',
            field=models.BooleanField(blank=True, default=True, verbose_name='Matcha inkommande Skype-samtal'),
        ),
        migrations.AddField(
            model_name='policyauthorizationoverride',
            name='match_incoming_webrtc',
            field=models.BooleanField(blank=True, default=False, help_text='Notera att denna är enkelt att skriva fake-värden, så använd i kombination med location', verbose_name='Matcha inkommande WebRTC-samtal'),
        ),
    ]
