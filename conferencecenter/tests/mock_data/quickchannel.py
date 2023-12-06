import json

from conferencecenter.tests.mock_data.response import FakeResponse

quickchannel_requests = {
    'GET bookrecording': (200, '''
    {
  "errormessage": "ERROR - There is no customer account registered for vmr myroom@mycorporation.com",
  "version": "v1.2.1",
  "servertimestamp": {},
  "destination_cam": "rtmp://streamingserver.site.com/app/streamname_cam1",
  "destination_vga": "rtmp://streamingserver.site.com/app/streamname_vga1",
  "presentationuri": "http://dev.quickchannel.com/qc/?play=37734",
  "vmr": "myroom@mycorporation.com",
  "filmid": 32732,
  "eventdatetime": "2017-02-12 10:00",
  "showtype": 3,
  "t1": "Recording and streaming booked",
  "t2": "Your booking starts at 2017-02-12 10:00 (in about 4 minutes). Would you like the recording to start automatically or do you prefer to start it manually?",
  "t3": "I want the recording to start automatically at the above time",
  "t4": "I want to manually start the recording later than 10:00",
  "endtime": "2017-02-12 10:05:00",
  "producer_id": "ability90"
}
    '''.strip()),
}


def quickchannel_post(self, url, *args, **kwargs):
    method = kwargs.pop('method', '') or 'POST'
    for call, response in list(quickchannel_requests.items()):

        if call in '%s %s' % (method, url):
            if isinstance(response, tuple):
                return FakeResponse(response[1], status_code=response[0])
            else:
                return FakeResponse(response)
    return FakeResponse(json.dumps({}), status_code=404)