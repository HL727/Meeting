from django.core.management.base import BaseCommand

from provider.ext_api.acano import AcanoAPI


class Command(BaseCommand):
    help = "Sync profiles"

    def handle(self, *args, **options):
        for provider in AcanoAPI.sync_profiles_all():
            print(str(provider).encode('utf-8'))
