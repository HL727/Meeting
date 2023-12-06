# Generated by Django 2.2.6 on 2020-03-31 15:46

from django.db import migrations, models
import django.db.models.deletion


def move_data(apps, schema):

    CustomerNameMatch = apps.get_model('customer.CustomerNameMatch')

    for name in CustomerNameMatch.objects.all():
        cm = name.customer_match
        cm.prefix_match = name.prefix_match
        cm.suffix_match = name.suffix_match
        cm.match_mode = name.match_mode
        cm.save()


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0002_auto_20200331_1642'),
    ]

    operations = [
        migrations.AddField(
            model_name='customermatch',
            name='match_mode',
            field=models.SmallIntegerField(choices=[(0, 'Either'), (1, 'Both')], default=0),
        ),
        migrations.AddField(
            model_name='customermatch',
            name='prefix_match',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='customermatch',
            name='suffix_match',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='customermatch',
            name='customer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Customer'),
        ),
        migrations.RunPython(move_data, migrations.RunPython.noop),
        migrations.DeleteModel(
            name='CustomerNameMatch',
        ),
    ]
