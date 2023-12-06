try:
    import ujson as json
except ImportError:
    import json
from ..models import Server
from django.utils.dateparse import parse_datetime
import gzip
from .acano import Parser as AcanoParser
from django.db import connection
from .utils import check_spam


def parse_file(server, fd, parser_cls=None):

    if not parser_cls:
        parser_cls = AcanoParser
    parser = parser_cls(server, debug=True)

    connection.set_autocommit(False)

    i = 0
    valid = 0
    last_valid = 0

    spam_queue = 0
    spam_date = None

    for line in fd:
        i += 1

        if valid != last_valid and valid % 100 == 0:
            print(valid, 'valid', i - valid, 'spam')
            last_valid = valid
            if spam_queue:
                parser.add_spam(spam_date, 'unknown_destination', spam_queue)
            spam_queue = 0
            connection.commit()

        line = line.decode('utf-8')
        if not line.startswith('{"') and not line.startswith('[') and '{"' in line:  # corrupt file
            line = line[line.find('{"'):]

        try:
            cur = json.loads(line)
            if not isinstance(cur, dict):
                continue

            if 'rawpost' not in cur:
                continue

            ip = cur.get('ip')

            cur = cur['rawpost']

            spam_count = check_spam(cur, ip)
            if spam_count is not None:
                spam_date = parse_datetime(cur.get('ts')).date()  # TODO multi date log file?
                spam_queue += spam_count
                continue
            valid += 1
        except Exception:
            continue

        if not cur:
            continue

        parser.parse_xml(cur)

    if spam_queue:
        parser.add_spam(spam_date, 'unknown_destination', spam_queue)

    connection.commit()
    connection.set_autocommit(True)


def handle_args(files, name=None, parser_cls=None):

    name = name or 'CMS'

    server = Server.objects.filter(customer__isnull=True).get_or_create(name=name, type=Server.ACANO)[0]

    for fname in files:
        if fname.endswith('.gz'):
            with gzip.open(fname) as fd:
                parse_file(server, fd, parser_cls=parser_cls)
        else:
            with open(fname) as fd:
                parse_file(server, fd, parser_cls=parser_cls)

