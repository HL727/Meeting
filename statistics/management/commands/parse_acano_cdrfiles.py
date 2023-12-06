from django.core.management.base import BaseCommand
from statistics.parser.commandline import handle_args


class Command(BaseCommand):
    help = "Parse CDR-files"

    def add_arguments(self, parser):
        parser.add_argument('files', metavar='filename', type=str, nargs='+',
                         help='filenames')
        parser.add_argument('--name', type=str, nargs='?',
                         help='Name of server')

    def handle(self, *args, **options):
        handle_args(options['files'], options['name'])
