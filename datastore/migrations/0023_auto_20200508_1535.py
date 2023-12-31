# Generated by Django 2.2.6 on 2020-05-08 13:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('datastore', '0022_conference_full_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='conference',
            name='call_id',
            field=models.CharField(blank=True, editable=False, max_length=200),
        ),
        migrations.AddField(
            model_name='conference',
            name='web_url',
            field=models.CharField(blank=True, editable=False, max_length=200),
        ),
        migrations.AlterField(
            model_name='cospaceaccessmethod',
            name='cospace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_methods', to='datastore.CoSpace'),
        ),
    ]
