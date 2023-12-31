# Generated by Django 2.1.4 on 2019-01-10 13:34

from django.db import migrations, models
import django.db.models.deletion
import mptt.fields


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cospaceunitrelation',
            name='unit',
            field=mptt.fields.TreeForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cospaces', to='organization.OrganizationUnit'),
        ),
        migrations.AlterField(
            model_name='organizationunit',
            name='name',
            field=models.CharField(max_length=200),
        ),
        migrations.AlterField(
            model_name='userunitrelation',
            name='unit',
            field=mptt.fields.TreeForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='users', to='organization.OrganizationUnit'),
        ),
    ]
