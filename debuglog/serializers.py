from rest_framework import serializers
from base64 import b64encode


class CompressedStoreBaseSerializer(serializers.ModelSerializer):

    content = serializers.SerializerMethodField()
    extra = serializers.DictField()
    paginate_by = 5

    def get_content(self, obj):
        try:
            if obj.content and (bytes(obj.content[:1]) in b'"{[' or bytes(obj.content).isdigit() or
                    bytes(obj.content) in [b'null', b'true', b'false']):
                return obj.content_json
        except ValueError:
            pass
        try:
            return obj.content_text
        except Exception:
            pass

        return b64encode(obj.content)

    class Meta:
        fields = (
                'url',
                'ts_created',
                'content',
                'extra',
                )


def get_serializer(model, extra_fields):

    mcls = model

    class Meta(CompressedStoreBaseSerializer.Meta):
        model = mcls
        fields = CompressedStoreBaseSerializer.Meta.fields + tuple(extra_fields or ())
        ref_name = model.__class__.__name__

    return type('{}Serializer'.format(model.__class__.__name__),
        (CompressedStoreBaseSerializer,), {'Meta': Meta})


