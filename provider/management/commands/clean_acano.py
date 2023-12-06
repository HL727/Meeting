from django.core.management.base import BaseCommand
from provider.ext_api.acano import AcanoAPI

class Command(BaseCommand):
    help = "Clean old acano meetings"

    def handle(self, *args, **options):

        AcanoAPI.unbook_expired()

