from django.core.management.base import BaseCommand
from provider.ext_api.clearsea import ClearSeaAPI

class Command(BaseCommand):
    help = "Clean old clearsea accounts"

    def handle(self, *args, **options):

        ClearSeaAPI.unbook_expired()

