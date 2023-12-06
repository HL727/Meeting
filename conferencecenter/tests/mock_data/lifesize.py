import json

from conferencecenter.tests.mock_data.response import FakeResponse

lifesize_requests = {
    'Scheduler_getUUID': '''
        {
          "buffer": "a60fb75f-3675-4c80-8a6f-f198462c0963",
          "_rv": 0
        }''',
    'Scheduler_getNextConferenceIdLong': '''
        {
          "conferenceId": 1023,
          "_rv": 0
        }
        ''',
    'Scheduler_getEventByUid': r'''
       {
      "buffer": "BEGIN:VEVENT\r\nUID:a60fb75f-3675-4c80-8a6f-f198462c0963\r\nSUMMARY:test name\r\nDESCRIPTION:test desc\r\nDTSTART:20140820T060000Z\r\nDTEND:20140820T070000Z\r\nTRANSP:OPAQUE\r\nRESOURCES:VIDEO=2 VOICE=0\r\nX-LIFESIZE:conferenceId=1023 password=12345 language=en_US \r\n videoCodecs=auto voiceCodecs=auto maxParticipantBitrate=0 \r\n maxAncVideoBitRatePercentage=0 presentations=on performanceMode=off \r\n presentationCodecs=auto register=true resolution=720p security=auto \r\n encoderSharing=unique audioOnly=false streaming=false expanded=false \r\n uiAnnouncements=on uiInput=dtmf uiInset=7 uiLayoutLocked=false \r\n uiUserControl=on uiLayoutName=auto uiOverlay=on uiSelfView=off \r\n uiTalkerOrder=on uiStickyNames=off uiAudioIntro=100 uiAudioDoor=100 \r\n uiPrintIntro=on uiPrintNames=on uiUserMenus=on fec=off vop=false \r\n createdByVop=false mediaServer=-1 profile= version= template=false \r\n region=-1 bridgeType=auto authName=auto \r\nCREATED:20140819T141159Z\r\nEND:VEVENT\r\n",
      "_rv": 1
    }
    ''',
}


def lifesize_post(self, url, data=None, **kwargs):
    for call, response in list(lifesize_requests.items()):
        if data and call in data:
            return FakeResponse(response)
    return FakeResponse(json.dumps({'meeting_id': 1, 'status': 'OK', '_rv': 0}))
