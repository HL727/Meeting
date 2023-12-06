import sys

from django.apps import AppConfig


class SharedAppConfig(AppConfig):

    name = 'shared'

    def ready(self):
        from shared.timescale import get_all_model_timescale_sql
        try:
            get_all_model_timescale_sql()
        except ValueError as e:
            sys.stderr.write('Model errors!\n{}'.format(e))

        from . import signals  # noqa
