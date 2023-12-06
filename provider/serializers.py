from rest_framework import serializers

from provider.models.provider import Provider, VideoCenterProvider, Cluster
from provider.models.vcs import VCSEProvider
from provider.models.provider_data import ProviderLoad


class ProviderLoadSerializer(serializers.ModelSerializer):

    percent = serializers.SerializerMethodField()

    def get_percent(self, obj):
        if obj.provider.max_load:
            return int(round(obj.load / obj.provider.max_load * 100))
        return None

    class Meta:
        model = ProviderLoad
        fields = ('ts_created', 'provider', 'load', 'percent', 'participant_count', 'bandwidth_in', 'bandwidth_out')


class ProviderSerializer(serializers.ModelSerializer):

    web_admin = serializers.SerializerMethodField(read_only=True)

    def get_web_admin(self, obj: Provider):
        return 'https://{}'.format(obj.api_host or obj.hostname or obj.ip)

    class Meta:
        model = Provider
        exclude = ('type', 'session_id', 'session_expires', 'options')
        extra_kwargs = {'password': {'write_only': True}}


class ProviderAdminSerializer(ProviderSerializer):

    class Meta(ProviderSerializer.Meta):
        exclude = ('type', 'session_id', 'session_expires', 'options')


class ProviderListSerializer(serializers.ModelSerializer):

    class Meta:
        model = Provider
        fields = ('title', 'id', 'cluster')


class ClusterSerializer(serializers.ModelSerializer):

    providers = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()

    def get_providers(self, obj):
        return ProviderListSerializer(obj.get_clustered(), many=True).data

    def get_type(self, obj):
        return {
            Provider.TYPES.acano_cluster: 'acano',
            Provider.TYPES.vcs_cluster: 'vcs',
            Provider.TYPES.pexip_cluster: 'pexip',
        }.get(obj.type) or 'other'

    class Meta:

        model = Cluster
        fields = ('title', 'id', 'providers', 'type')


class ClusterAdminSerializer(ClusterSerializer):

    cdr_url = serializers.SerializerMethodField(read_only=True)
    policy_url = serializers.SerializerMethodField(read_only=True)

    def get_cdr_url(self, obj: Cluster):
        return obj.get_statistics_server().get_cdr_url()

    def get_policy_url(self, obj: Cluster):
        from policy.models import ClusterPolicy
        policy = ClusterPolicy.objects.filter(cluster=obj).first()
        return policy.get_absolute_url() if policy else ''

    class Meta(ClusterSerializer.Meta):
        fields = ClusterSerializer.Meta.fields + ('cdr_url', 'policy_url')


class VCSProviderSerializer(serializers.ModelSerializer):

    class Meta:
        model = VCSEProvider
        exclude = ('session_id', 'session_expires')
        extra_kwargs = {'password': {'write_only': True}}


class RecordingProviderSerializer(serializers.ModelSerializer):

    class Meta:
        model = VideoCenterProvider
        exclude = ('session_id', 'session_expires')
        extra_kwargs = {'password': {'write_only': True}}
