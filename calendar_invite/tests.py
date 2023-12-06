import re
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Union

import pytz
from django.test.testcases import TestCase
from django.utils.timezone import now, utc

from msgraph.parser import MSGraphParser
from .parser import InviteMessageParser
from provider.models.utils import date_format


DEFAULT_CONTACT = '12345@example.call.sl'


def _get_vcard():
    data = re.sub(r'^\s+', '', '''
    BEGIN:VCARD
    VERSION:3.0
    FN:Test av inspelning
    N:;Test av inspelning
    URL:breeze://1234@example.org
    ORG:StarLeaf
    END:VCARD
    ''', flags=re.MULTILINE).strip()

    return data


def _get_icalendar(ts_start=None, uid='uid1@example.com', desc='Desc', contact='', status='CONFIRMED', is_private=False, extra_ical=None, timezone=None):

    ts_start = ts_start or now() + timedelta(seconds=90)

    if extra_ical and 'RRULE' in extra_ical:
        extra_ical = 'RECURRENCE-ID;TZID=UTC:{}\n{}'.format(date_format(ts_start), extra_ical)

    if timezone in (None, False):
        formatted_ts_start = 'DTSTART:{}'.format(date_format(ts_start))
        formatted_ts_stop = 'DTEND:{}'.format(date_format(ts_start + timedelta(hours=1)))
    else:
        timezone = timezone if isinstance(timezone, str) else 'Europe/Stockholm'
        def _remove_tz(ts):
            return ts.astimezone(pytz.timezone(timezone)).replace(tzinfo=None).replace(tzinfo=utc)
        formatted_ts_start = 'DTSTART;TZID={}:{}'.format(timezone, date_format(_remove_tz(ts_start))).rstrip('Z')
        formatted_ts_stop = 'DTEND;TZID={}:{}'.format(timezone, date_format(_remove_tz(ts_start + timedelta(hours=1)))).rstrip('Z')

    data = re.sub(r'^\s+', '', '''
    BEGIN:VCALENDAR
    PRODID:test
    VERSION:3.0
    BEGIN:VEVENT
    UID:{}
    ORGANIZER:mailto:jsmith@example.com
    {}
    {}
    CONTACT:{}
    CATEGORIES:CONFERENCE
    SUMMARY:Test
    DESCRIPTION:{}
    STATUS:{}
    {}
    {}
    END:VEVENT
    END:VCALENDAR
    '''.format(uid, formatted_ts_start, formatted_ts_stop,
               contact or DEFAULT_CONTACT, desc, status, 'CLASS:PRIVATE' if is_private else '',
               extra_ical or ''), flags=re.MULTILINE).strip()

    return data


def _get_full_message(mode='record', content=None, cc=None, calendar: Union[bool, str] = True, vcard=True):

    msg = MIMEMultipart()
    msg['Subject'] = 'Subject'
    msg['To'] = '{}@book.example.org'.format(mode)
    if cc:
        msg['CC'] = cc
    msg['From'] = 'sender@example.org'
    msg['Message-ID'] = 'asdfg'

    if calendar:
        if calendar is True:
            calendar = _get_icalendar()
        cal = MIMEText(calendar, _subtype='calendar')
        msg.attach(cal)

    if vcard:
        vcard = MIMEText(_get_vcard(), _subtype='x-vcard')
        msg.attach(vcard)

    text = MIMEText(content or '', 'plain')
    msg.attach(text)

    msg.preamble = content or ''

    return msg


class ParserTest(TestCase):

    def get_match(self, text_content):
        from emailbook.handler import EmailHandler
        handler = EmailHandler(_get_full_message(mode='record', vcard=False, calendar=False,
                                                 content=text_content).as_string())

        valid, content, error = handler.validate()
        if content.get('dialstring') and '"' not in text_content:
            with_quote = self.get_match('<a href="{}">{}</a>'.format(text_content.strip(), 'test'))
            self.assertFalse('"' in with_quote.get('dialstring', ''), with_quote.get('dialstring'))
            self.assertEqual(content.get('dialstring'), with_quote.get('dialstring'))
        return content

    def test_text(self):

        result = self.get_match('''
        1234@example.org
        ''')

        self.assertEqual(result['dialstring'], '1234@example.org')

        result = self.get_match('''
        sip:555@example.org
        test234@example.org
        1234@example.org
        ''')

        self.assertEqual(result['dialstring'], '555@example.org')

    def test_numeric_fallback(self):

        data = '''
        test234@example.org
        1234@example.org
        '''

        result = self.get_match(data)
        self.assertEqual(result.get('dialstring'), '1234@example.org')

    def test_text_fallback(self):

        data = '''
        test234@example.org
        test.vr@example.org
        '''

        result = self.get_match(data)
        self.assertEqual(result.get('dialstring'), 'test.vr@example.org')

    def test_vcard(self):

        result = InviteMessageParser().parse_vcard(_get_vcard())
        self.assertEqual(result['dialstring'], '1234@example.org')

    def test_cancelled(self):

        ts_start = now()
        result = InviteMessageParser().parse_calendar(_get_icalendar(ts_start=ts_start))
        self.assertEqual(result.get('cancelled'), None)

        result = InviteMessageParser().parse_calendar(_get_icalendar(ts_start=ts_start, status='CANCELLED'))
        self.assertEqual(result['cancelled'], True)

    def test_calendar(self):

        ts_start = now()
        result = InviteMessageParser().parse_calendar(_get_icalendar(ts_start=ts_start))
        self.assertEqual(date_format(result['ts_start'])[:-3], date_format(ts_start)[:-3])

    def test_starleaf(self):
        content = self.get_match(DEFAULT_CONTACT)
        self.assertEqual(content['dialstring'], '12345@example.call.sl')

    def test_teams(self):
        content = self.get_match('Test call to https://pexip.me/teams/teams.example.org/123456 ')
        self.assertEqual(content['dialstring'], '123456@teams.example.org')

    def test_teams_cvi(self):
        content = self.get_match('https://pex-edge01.pex.example.org/teams/?conf=abcd.1337194408&ivr=abcd&d=pex.example.org&ip=127.0.0.1')
        self.assertEqual(content['dialstring'], 'abcd.1337194408@pex.example.org')

        content = self.get_match('https://pex-edge01.pex.example.org/teams/?conf=abcd.1337194408&ivr=abcd&d=pex.example.org&prefix=aaa')
        self.assertEqual(content['dialstring'], 'aaaabcd.1337194408@pex.example.org')

    def test_lifesize(self):
        content = self.get_match('Test call to https://call.lifesizecloud.com/12345 ')
        self.assertEqual(content['dialstring'], '12345@sip.lifesizecloud.com')

    def test_sip_fallback(self):
        content = self.get_match('Call me att 123456@example.org')
        self.assertEqual(content['dialstring'], '123456@example.org')

    def test_h323_fallback(self):
        content = self.get_match('Call me att 123.123.123.123##1234')
        self.assertEqual(content['dialstring'], '123.123.123.123##1234')

    def test_bluejeans(self):
        content = self.get_match('''
        To join the meeting on a computer or mobile phone: https://bluejeans.com/184405040?src=calendarLink


One Touch Dial-in:
+14087407256,,,184405040#
''')
        self.assertEqual(content['dialstring'], '184405040@bjn.vc')

    def test_bluejeans_teams(self):
        content = self.get_match('''
    Join Microsoft Teams Meeting
    +46 8 505 218 52   Sweden, Stockholm (Toll)
    Conference ID: 269 926 001#
    Local numbers | Reset PIN | Learn more about Teams | Meeting options
    Join with a video conferencing device
    130885042@teams.bjn.vc VTC Conference ID: 1291418361
    Alternate VTC dialing instructions
''')
        self.assertEqual(content['dialstring'], '130885042.1291418361@teams.bjn.vc')

    def test_cms_invite(self):
        invite = '''
            You're invited to Test meeting

Click to join: https://join.demo.mividas.com/invited.sf?secret=asdf.345&id=12345


To call with: Video system, Spark, Skype for Business/Lync: make video call to test@demo.mividas.com
        '''
        content = self.get_match(invite)
        self.assertEqual(content['dialstring'], '12345@join.demo.mividas.com')

        # web join rewrite
        from provider.models.provider import Provider
        Provider.objects.create(subtype=Provider.SUBTYPES.acano, hostname='test',
                                web_host='join.demo.mividas.com', internal_domains='demo.mividas.com')

        content = self.get_match(invite)
        self.assertEqual(content['dialstring'], '12345@demo.mividas.com')

    def test_webex_invite(self):
        content = self.get_match('''
Join from a video conferencing system or application

Meeting link: https://mividas.webex.com/meet/test.user?a=4

        ''')
        self.assertEqual(content['dialstring'], 'test.user@mividas.webex.com')

    def test_webex_lync_invite(self):
        content = self.get_match('''
Join using Microsoft Skype for Business: test.user.mividas@lync.webex.com

        ''')
        self.assertEqual(content['dialstring'], 'test.user@mividas.webex.com')


    def test_acano_webrtc(self):
        content = self.get_match('''

https://public.webrtc.com/invited.sf?id=764538600&secret=iabbbbbbb

764538600@sip.example.org

        ''')
        self.assertEqual(content['dialstring'], '764538600@sip.example.org')

        content = self.get_match('''https://public.webrtc.com/invited.sf?id=764538600&secret=iabbbbbbb''')
        self.assertEqual(content['dialstring'], '764538600@public.webrtc.com')

    def test_acano_webrtc2(self):
        content = self.get_match('''

https://cms30.demo.mividas.com/index.html?id=123456&secret=iabbbbbbb

        ''')
        self.assertEqual(content['dialstring'], '123456@cms30.demo.mividas.com')

    def test_acano_webapp(self):
        content = self.get_match('''
https://cms30.demo.mividas.com/meeting/123456?test

        ''')
        self.assertEqual(content['dialstring'], '123456@cms30.demo.mividas.com')

    def test_pexip_cvi_webapp(self):
        content = self.get_match('''
            Test <a href="https://teams.microsoft.com/l/meetup-join/19%3ameeting_Y2RhZTA0ZWQtNzEyOC00MWU4LTk3ZDAtZWRiNzBhYjJkMWMw%40threa">test</a>\n
            <a href="https://gw.pexip.mividas.org/teams/?conf=1234&amp;ivr=teams&amp;d=domain.mividas.com&amp;ip=1.2.3.4&amp;test=test_call&amp;w"><font face="Segoe UI" size="2" color">test</font></a>
            ''')
        self.assertEqual(content['dialstring'], '1234@domain.mividas.com')

    def test_pexip_v25_webapp(self):
        content = self.get_match('''
https://video.mividas.com/webapp/home/?conference=1234@example.org
        ''')
        self.assertEqual(content['dialstring'], '1234@example.org')

        content = self.get_match('''
https://video.mividas.com/webapp/#/?conference=1234@example.org
        ''')
        self.assertEqual(content['dialstring'], '1234@example.org')

    def test_pexip_v24_webapp(self):
        content = self.get_match('''
https://video.mividas.com/webapp/conference/1234@example.org?test=1
        ''')
        self.assertEqual(content['dialstring'], '1234@example.org')


    def test_webex_vtc(self):
        content = self.get_match('''
<div><a href="https://teams.microsoft.com/l/meetup-join/19%3ameeting_345345i00MWZlLWEzY2YtNTIy5445Fm%40thread.v2/0?context=%7b%22Tid%22%3a%2240da1707-911d-40c5-af74-c5390f112ea4%22%2c%22Oid%22%3a%2234456456456-c7b3-4cbd-a48a-d3c623388d80%22%7d" target="_blank" rel="noopener noreferrer" data-auth="NotApplicable"><u>Liity
 34346 234</u></a>
</div>
<div><b>344334</b>
</div>
<div><a href="mailto:mividas@m.webex.com" target="_blank" rel="noopener noreferrer" data-auth="NotApplicable"><u>mividas@m.webex.com</u></a>
</div>
<div>Videoneuvottelun tunnus:
125 977 202 6 </div>
<div><a href="https://www.webex.com/msteams?confid=1259772026&amp;tenantkey=mividas&amp;domain=m.webex.com" target="_blank" rel="noopener noreferrer" data-auth="NotApplicable"><u>Vaihtoehtoiset
 VTC-liittymisohjeet</u></a>
</div>
<div><a href="https://aka.ms/JoinTeamsMeeting" target="_blank" rel="noopener noreferrer" data-auth="NotApplicable"><u>sdg4545gf</u></a>
 | <a href="https://teams.microsoft.com/meetingOptions/?organizerId=34456456456-c7b3-4cbd-a48a-d3c623388d80&amp;tenantId=40da1707-911d-40c5-af74-c5390f112ea4&amp;threadId=19_meeting_345345i00MWZlLWEzY2YtNTIy5445Fm@thread.v2&amp;messageId=0&amp;language=fi-FI" target="_blank" rel="noopener noreferrer" data-auth="NotApplicable"><u>Kokousasetukset</u></a>
</div>
<div>________________________________________________________________________________
</div>
<div>&nbsp;</div>
<div>&nbsp;</div>
</span></font>        ''')
        self.assertEqual(content['dialstring'], '1259772026.mividas@m.webex.com')

    def test_zoom(self):
        content = self.get_match('''
        <b>Missä:</b> https://something.zoom.us/j/545096111?pwd=YXRsN13434534534543</p>\
\r\n&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 877 853 5257 US Toll-free<br>\r\nMeeting ID: 545 096 0756<br>\r\nPasscode: 623458<br>\r\nFind your local number: <a href="..." target="_blank">\r\nhttps://something.zoom.us/u/asdf</a></span></p>\r\n<p><span style="font-size:10.0pt; font-family:&quot;Arial&quot;,sans-serif; color:#222222">
Join by SIP<br>\r\n<a href="mailto:545096111@zoomcrc.com" target="_blank">545096111@zoomcrc.com</a></span></p>\r\n<p><span style="font-size:10.0pt; font-family:&quot;Arial&quot;,sans-serif; color:#222222">Join by H.323<br>\r\n162.255.37.11 (US West)<br>\r\n162.255.36.11 (US East)'''
                                 )
        self.assertEqual(content['dialstring'], '545096111.623458@zoomcrc.com')
        self.assertEqual(content['webrtc'], 'https://something.zoom.us/j/545096111?pwd=YXRsN13434534534543')

    def test_skype(self):

        ical = r'''
BEGIN:VCALENDAR
METHOD:REQUEST
PRODID:Microsoft Exchange Server 2010
VERSION:2.0
BEGIN:VTIMEZONE
TZID:W. Europe Standard Time
BEGIN:STANDARD
DTSTART:16010101T030000
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
RRULE:FREQ=YEARLY;INTERVAL=1;BYDAY=-1SU;BYMONTH=10
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:16010101T020000
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
RRULE:FREQ=YEARLY;INTERVAL=1;BYDAY=-1SU;BYMONTH=3
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VEVENT
ORGANIZER:MAILTO:test.tset@example.se
ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:MAILTO:john@m
 ividas.com
DESCRIPTION;LANGUAGE=sv-SE:\n..............................................
 ..........................................................................
 .................\nAnslut till Skype-mötet <https://meet.example.
 se/test.tset/6N2YGD5G>\nAnslutningsproblem? Prova Skype Web App <https://
 meet.example.se/test.tset/6N2YGD5G?sl=1>\nAnslut via telefon\n+46
 19123<tel:+234324324> (Sweden)
     Svenska (Sverige)\nHitta ett lokalt nummer <https://dialin.rrrrrrrrrrr
 olan.se>\n\nKonferens-ID: 68138\n Har du glömt din PIN-kod för uppringni
 ng? <https://dialin.example.se>  |Hjälp <https://support.office.c
 om/sv-SE/article/Ansluta-till-ett-Lync-m%c3%b6te-5b651989-50f2-407f-9b17-c
 d40b83c1681?ui=sv-SE&rs=sv-SE&ad=SE>\n\n[https://lyncweb.test.se/logo_
 stor.png]\nFör videosystem och Jabber\, ring till 21033@example.s
 e<mailto:21033@example.se> (inom regionen räcker det med 21033) o
 ch ange Konferens-ID ovan\, avsluta med #.\n[!OC([041d])!]\n..............
 ..........................................................................
 .................................................\n\n
UID:040000008200E00074C5B7101A82E0080000000020E92608D806D801000000000000000
 010000000D389325D2545CD49BDC437228AC138CA
SUMMARY;LANGUAGE=sv-SE:Testmöte
DTSTART;TZID=W. Europe Standard Time:20220111T110000
DTEND;TZID=W. Europe Standard Time:20220111T113000
CLASS:PUBLIC
PRIORITY:5
DTSTAMP:20220111T094312Z
TRANSP:OPAQUE
STATUS:CONFIRMED
SEQUENCE:0
LOCATION;LANGUAGE=sv-SE:Skype-möte
X-MICROSOFT-CDO-APPT-SEQUENCE:0
X-MICROSOFT-CDO-OWNERAPPTID:-999614490
X-MICROSOFT-CDO-BUSYSTATUS:TENTATIVE
X-MICROSOFT-CDO-INTENDEDSTATUS:BUSY
X-MICROSOFT-CDO-ALLDAYEVENT:FALSE
X-MICROSOFT-CDO-IMPORTANCE:1
X-MICROSOFT-CDO-INSTTYPE:0
X-MICROSOFT-ONLINEMEETINGEXTERNALLINK:https://meet.example.se/test
 .test/6N2YGD5G
X-MICROSOFT-ONLINEMEETINGCONFLINK:conf:sip:test.tset@example.se\;g
 ruu\;opaque=app:conf:focus:id:6N2YGD5G?conversation-id=E2KM0wvqb7
X-MICROSOFT-CONFERENCETELURI:tel:+4612345\,\,68138
X-MICROSOFT-DONOTFORWARDMEETING:FALSE
X-MICROSOFT-DISALLOW-COUNTER:FALSE
BEGIN:VALARM
DESCRIPTION:REMINDER
TRIGGER;RELATED=START:-PT15M
ACTION:DISPLAY
END:VALARM
END:VEVENT
END:VCALENDAR
        '''

        result = InviteMessageParser().parse_calendar(ical.strip())

        self.assertEqual(result['dialstring_fallback'], '21033@example.se')
        self.assertEqual(result['skype_conference_id'], '68138')

        # fallback method, remove description
        result = InviteMessageParser().parse_calendar(
            ical.strip().replace('Konferens-ID:', 'Konferens-XX:')
        )

        self.assertEqual(result['dialstring_fallback'], '21033@example.se')
        self.assertEqual(result['skype_conference_id'], '68138')
