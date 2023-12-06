from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sync data from CMS server and ldap"

    def handle(self, *args, **options):

        from provider import tasks

        tasks.cache_cluster_data(incremental=False)
        tasks.cache_ldap_data()

