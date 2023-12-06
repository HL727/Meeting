from rest_framework import serializers

from theme.models import Theme


class ThemeSerializer(serializers.ModelSerializer):

    logo_image = serializers.FileField(required=False, allow_null=True)
    favicon = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = Theme
        fields = (
            'id',
            'logo_image',
            'favicon',
            'dark_mode'
        )
        read_only_fields = ('id',)
