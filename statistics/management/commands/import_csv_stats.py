from django.core.management.base import BaseCommand
from os import environ

from statistics.mividas_csv import mividas_csv_import_multiprocess


class Command(BaseCommand):
    help = "Import Mividas CSV export"

    def add_arguments(self, parser):
        parser.add_argument('server_id', type=int, help='Name of server')
        parser.add_argument('type', type=str, help='call or leg')
        parser.add_argument('files', metavar='filename', type=str, nargs='+', help='filenames')

    def handle(self, *args, **options):
        assert options['type'] in ('call', 'leg')

        processes = None
        if environ.get('PROCESSES'):
            processes = int(environ.get('PROCESSES'))

        for filename in options['files']:

            for l in mividas_csv_import_multiprocess(options['server_id'], options['type'], filename, processes=processes):
                print(l)
