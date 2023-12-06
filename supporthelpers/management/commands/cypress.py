from django.core.management.base import BaseCommand
import subprocess


class Command(BaseCommand):
    help = 'Runs Cypress tests'

    def handle(self, *args, **options):
        subprocess.call(['npm', 'run', 'cypress:run'])


