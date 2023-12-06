from django.core.management.base import BaseCommand
from statistics.parser.commandline import handle_args


class Command(BaseCommand):
    help = "Parse CDR-files"

    def handle(self, *args, **options):
        from statistics.parser.vcse import VCSEParser
        handle_args(args, parser_cls=VCSEParser)
