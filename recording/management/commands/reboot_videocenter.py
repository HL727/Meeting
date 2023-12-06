from django.core.management.base import BaseCommand
from customer.models import Customer
from provider.models.provider import VideoCenterProvider


class Command(BaseCommand):
    help = "Reboot videocenters"

    def add_arguments(self, parser):
        parser.add_argument('ids', nargs='+')

    def handle(self, *args, **options):
        customer = Customer.objects.all()[0]

        for vc in VideoCenterProvider.objects.filter(pk__in=options['ids']):
            vc.get_api(customer).reboot()
