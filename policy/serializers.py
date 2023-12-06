from rest_framework import serializers

from policy.models import CustomerPolicy, CustomerPolicyState, PolicyLog, ExternalPolicyLog, ActiveParticipant


class PolicySerializer(serializers.Serializer):

    ts_start = serializers.DateTimeField(required=False)
    ts_stop = serializers.DateTimeField(required=False)
    server = serializers.IntegerField(required=False)

    as_graph = serializers.BooleanField(required=False)


class CustomerPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerPolicy
        fields = ('id', 'customer', 'participant_limit', 'participant_hard_limit', 'date_start')


class CustomerPolicyLimitSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()
    name = serializers.CharField(source='customer.title')

    class Meta:
        model = CustomerPolicy
        fields = ('customer', 'name', 'participant_limit', 'participant_hard_limit', 'state')

    def get_state(self, obj):
        customer_state = self.context['states'].get(obj.customer_id, None)

        if not customer_state:
            return None

        state_serializer = CustomerPolicyStateSerializer(customer_state)
        return state_serializer.data


class CustomerPolicyStateSerializer(serializers.ModelSerializer):

    class Meta:
        model = CustomerPolicyState
        fields = ('id', 'customer', 'cluster', 'active_calls', 'participant_value', 'active_participants', 'participant_status', 'last_check')


class PolicyLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyLog
        fields = ('id', 'ts', 'customer', 'message', 'guid', 'level', 'type', 'cluster', 'source')


class ExternalPolicyLogSerializer(serializers.ModelSerializer):

    class Meta:
        model = ExternalPolicyLog
        fields = ('id', 'ts', 'customer', 'message', 'limit', 'action', 'conference', 'local_alias', 'remote_alias', 'cluster')


class ActiveParticipantSerializer(serializers.ModelSerializer):

    class Meta:
        model = ActiveParticipant
        fields = ('id', 'ts_created', 'cluster', 'customer', 'guid', 'name', 'is_gateway', 'cluster')


class LegDebugFilterSerializer(serializers.Serializer):

    guid = serializers.CharField(max_length=500)
    ts_start = serializers.DateTimeField(required=False)


class LegDebugSerializer(serializers.Serializer):

    legs = serializers.ListField(child=serializers.DictField())
    cdr = serializers.ListField(child=serializers.DictField())
    history = serializers.ListField(child=serializers.DictField())
