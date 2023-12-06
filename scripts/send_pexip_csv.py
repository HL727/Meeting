import csv
import hashlib
import json
import sys
from datetime import datetime
from urllib.request import urlopen, Request
from collections import namedtuple
from time import sleep

PARTICIPANT_FILENAME = ''
CONFERENCE_FILENAME = ''

IGNORE_ITEMS_UNTIL = '2020-04-03T00:00:00'

URL = 'https://example.mividas.com/cdr/pexip/1234/{}/csv/'

sent_conf = set()
sent_part = set()

sys.encoding = 'utf-8'

def _iter_unique(iterable):

	processed = set()
	tuple_processed = set()
	for cols in iterable:
		if not cols:
			continue

		tuple_hash = hash(tuple(cols))


		cur_hash = hashlib.sha1(','.join(cols).encode('utf-8')).digest()
		if cur_hash in processed:
			continue

		if tuple_hash in tuple_processed:
			print('tuple diff', cols)
		tuple_processed.add(cur_hash)

		processed.add(cur_hash)
		try:  # powershell script encoder bug
			cols = [c.encode('latin1').decode('utf-8') for c in cols]
		except (UnicodeEncodeError, UnicodeDecodeError):
			pass


		replace = {
			'None': None,
			'True': True,
			'False': False,
			'System.Object[]': None,
		}
		yield [replace.get(c, c) for c in cols]


queue = []

def _send(type, item, cols, force=False):

	if item:
		queue.append(item)
	if len(queue) < 1000:
		if not force:
			return

	def _request():

		data = {
			'cols': cols._fields,
			'rows': queue,
		}

		request = Request(URL.format(type), json.dumps(data).encode('utf-8'), headers={'Content-Type': 'text/json'})

		with urlopen(request) as response:
			if response.getcode() not in (200, 201):
				raise Exception('Invalid status: {}'.format(response.getcode()), response.read())

			return True

	error = None
	for i in range(5):
		try:
			_request()
		except Exception as e:
			error = e
			print(datetime.now().replace(microsecond=0).isoformat(), 'Error {}'.format(e))
			sleep(5 + i * 15)
		else:
			print(datetime.now().replace(microsecond=0).isoformat(), 'Sent', len(queue), type, 'first start time', queue[0][cols.start_time])
			queue[:] = []
			break
	else:
		raise error


conf_csv = csv.reader(open(CONFERENCE_FILENAME, encoding='utf-8'))

cols = None
i = 0
for i, conf in enumerate(_iter_unique(conf_csv)):
	if i == 0:
		cols = namedtuple('ConfHeader', conf)(*range(len(conf)))
		continue
	if not conf or (IGNORE_ITEMS_UNTIL and IGNORE_ITEMS_UNTIL > conf[cols.start_time].replace(' ', 'T')):
		continue

	if 'IVR' in conf[cols.name]:
		continue

	_send('conference', conf, cols)

_send('conference', {}, cols, force=True)

print(i)
#sys.exit()  # FIXME

part_csv = csv.reader(open(PARTICIPANT_FILENAME, encoding='utf-8'))


cols = None
for i, part in enumerate(_iter_unique(part_csv)):
	if i == 0:
		cols = namedtuple('PartHeader', part)(*range(len(part)))
		continue

	if not part or not part[cols.start_time]:
		continue

	if IGNORE_ITEMS_UNTIL and IGNORE_ITEMS_UNTIL > part[cols.start_time].replace(' ', 'T'):
		continue

	if part[cols.service_type] in ('ivr', 'two_stage_dialing'):
		continue

	_send('participant', part, cols)

_send('participant', {}, cols, force=True)


print(i)
