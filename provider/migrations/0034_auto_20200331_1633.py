# Generated by Django 2.2.6 on 2020-03-31 14:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('provider', '0033_customer_pexip_tenant_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='pexip_tenant_id',
            field=models.CharField(blank=True, help_text='Genereras automatiskt', max_length=65, verbose_name='Pexip tenant-id'),
        ),
        migrations.AlterField(
            model_name='pexipspace',
            name='cluster',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='provider.Provider'),
        ),
    ]
