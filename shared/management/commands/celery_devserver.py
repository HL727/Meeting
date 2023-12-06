from threading import Thread
from time import sleep

from django.core.management.commands.runserver import Command as RunServer
from django.utils import autoreload


class Command(RunServer):
    help = "runserver + celery"
    controller = None

    def run(self, *args, **options):
        return autoreload.run_with_reloader(self.inner_run, *args, **options)

    def inner_run(self, *args, **options):

        from conferencecenter.celery import app

        from celery.apps.worker import Worker
        from celery.concurrency import get_implementation

        from django.core import management
        management.execute_from_command_line(['manage.py', 'upgrade_installation'])

        if self.controller:
            self.controller.terminate()
        self.controller = Worker(app=app, quiet=False, pool_cls=get_implementation('solo'), log_level='INFO')
        t = Thread(target=self.controller.start)
        t.start()
        try:
            super().inner_run(*args, **options)
        finally:
            self.controller.stop()
