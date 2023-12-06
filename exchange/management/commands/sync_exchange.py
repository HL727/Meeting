from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sync exchange data"

    def handle(self, *args, **options):
        from exchange.tasks import poll_ews, sync_ews_rooms
        poll_ews()
        sync_ews_rooms()
