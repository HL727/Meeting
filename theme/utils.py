from .models import Theme
from .serializers import ThemeSerializer


def get_theme_instance():
    return Theme.objects.get_or_create(pk=1)[0]


def get_theme_settings():
    theme = get_theme_instance()

    return ThemeSerializer(theme).data
