from rest_framework import serializers


class LdapSyncParamsSerializer(serializers.Serializer):
    all = serializers.BooleanField(label='Sync all tenants', required=False, help_text='CMS only')


class StatusResponseSerializer(serializers.Serializer):

    status = serializers.ChoiceField(choices=('OK', 'error'))
    error = serializers.CharField(allow_blank=True)
