from rest_framework import serializers


class GraphSerializer(serializers.Serializer):

    layout = serializers.DictField()
    graph = serializers.DictField()


class CountSerializer(serializers.Serializer):

    graphs = serializers.DictField()
    layout = serializers.DictField()


class PolicyReportResponseSerializer(serializers.Serializer):

    soft_limit = serializers.DictField(child=serializers.DictField(child=GraphSerializer()), allow_null=True)
    soft_limit_30 = serializers.DictField(child=serializers.DictField(child=GraphSerializer()), allow_null=True)
    hard_limit = serializers.DictField(child=serializers.DictField(child=GraphSerializer()), allow_null=True)
    count = serializers.DictField(child=serializers.DictField(child=CountSerializer()), allow_null=True)
