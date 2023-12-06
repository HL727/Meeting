from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Send user stats to portal"

    def handle(self, *args, **options):
        from statistics.models import Leg
        Leg.objects.send_stat_summaries()
