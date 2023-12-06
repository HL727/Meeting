from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Fetch and update pexip stats"

    def handle(self, *args, **options):
        from provider.ext_api.pexip import PexipAPI
        PexipAPI.update_all_pexip_stats(incremental=False)
