from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Fetch and update vcse stats"

    def handle(self, *args, **options):
        from provider.ext_api.vcse import VCSExpresswayAPI
        VCSExpresswayAPI.update_all_vcs_stats()
