import html
import re
from hashlib import md5
from typing import Dict, Sequence, Callable, Optional
from urllib.parse import parse_qsl

from django.conf import settings
from django.core.cache import cache
from django.db.models import F
from django.utils.encoding import force_bytes
from django.utils.formats import date_format
from ics import Calendar, Event
from sentry_sdk import capture_exception

from calendar_invite.types import InviteMessageParseDict
from .ical import monkey_patch_ics

ENABLE_SKYPE = False  # Don't know if it's ever possible to call skype meetings
ENABLE_TEAMS_LOCATION = False  # Try to match MS location of the room as fallback
ALLOW_SCRAPE = True


monkey_patch_ics()


class InviteMessageParser:

    def __init__(self):
        self.allow_scrape = ALLOW_SCRAPE

    def parse(self) -> InviteMessageParseDict:
        raise NotImplementedError()

    def _ics_parse_with_timezone_fix(self, text):
        import ics
        timezonescalendar = Calendar(text)
        calendar = Calendar()
        calendar._timezones = timezonescalendar._timezones
        containers = ics.icalendar.calendar_string_to_containers(text)
        assert len(containers) == 1
        calendar._populate(containers[0])
        return calendar

    def parse_calendar(self, text):

        if isinstance(text, bytes):
            try:
                text = text.decode('utf-8')
            except UnicodeDecodeError:
                text = text.decode('latin1')

        text = re.sub(r'TRIGGER;RELATED=.*', 'TRIGGER;VALUE=DATE-TIME:19980101T050000Z', text)  # TODO support for TRIGGER;RELATED=START:-PT15M
        cal = self._ics_parse_with_timezone_fix(text)

        results = [self.parse_calendar_event(event) for event in cal.events]
        if not results:
            return {}

        # starleaf sometimes write sipurl in ics as CONTACT
        match_contact = re.search(r'^CONTACT: ?(\d+@[^.]+\.?call.sl)', text, re.MULTILINE)
        if match_contact:
            for r in results:
                r.setdefault('dialstring', match_contact.group(1))

        result, *other_events = results
        if other_events:
            exceptions, extra_events, _other_events = self.get_exceptions_from_events(result, other_events)
            if extra_events:
                result['is_recurring'] = True

            # Make sure to separate extra_events from recurring serie,
            # or add to RecurringMeeting.recurring_overrides
            result['recurring_exceptions'], result['extra_events'] = exceptions, extra_events

        return result

    def get_exceptions_from_events(self, first_event: Dict, other_events: Sequence[Dict]):

        exdate = first_event['recurring_exceptions'].split(',') if first_event.get('recurring_exceptions') else []

        related_events = [o for o in other_events if o['uid'] == first_event['uid']]
        other_events = [o for o in other_events if o['uid'] != first_event['uid']]

        for related in related_events:

            if related.get('uid') == first_event.get('uid'):
                exdate.append(first_event.get('recurrence_id') or date_format(first_event['ts_stop']))

        return ','.join(exdate), related_events, other_events

    def parse_calendar_event(self, event: Event):

        result = {
            'ts_start': event.begin.datetime,
            'ts_stop': event.end.datetime,
            'timezone': event.begin.tzinfo,
            'uid': event.uid,
        }

        if event.name and event.name.strip():
            result['subject'] = event.name.strip()

        if hasattr(event, 'recurrence_id'):
            result['recurrence_id'] = event.recurrence_id

        if getattr(event, 'classification', None):
            result['is_private'] = event.classification.upper() == 'PRIVATE'
        if hasattr(event, 'rrule'):
            result['recurring'] = event.rrule
        if hasattr(event, 'exdate'):
            result['recurring_exceptions'] = event.exdate

        text_matches = self.parse_text(event.location) if event.location else {}

        if not text_matches.get('dialstring') and event.description:
            text_matches.update(self.parse_text(event.description or '') or {})
            result['has_body'] = True

        result.update(text_matches)

        if hasattr(event, 'ms_locations') and isinstance(event.ms_locations, list) and ENABLE_TEAMS_LOCATION:
            for loc in event.ms_locations:
                if not isinstance(loc, dict) or not loc.get('LocationUri'):
                    continue
                uri = loc.get('LocationUri')
                if '@' in uri and not uri.startswith('mailto:') and '://' not in uri and ' ' not in uri:
                    result['dialstring_fallback'] = uri

        if hasattr(event, 'skype'):
            if event.skype.startswith('conf:sip:'):
                result['skype_conference'] = event.skype.replace('\\', '')  # TODO skype conference dial support?

                skype_conference = self._match_skype_conference_id(
                    event.description or '', event.description or ''
                )
                if skype_conference and skype_conference.get('skype_conference_id'):
                    result['skype_conference_id'] = skype_conference['skype_conference_id']
                else:
                    conference_uris = [
                        e for e in event.extra if e.name == 'X-MICROSOFT-CONFERENCETELURI'
                    ]
                    if conference_uris:
                        m = re.search(',(\d+)$', conference_uris[0].value.strip())
                        if m:
                            result['skype_conference_id'] = m.group(1)

            if ENABLE_SKYPE:
                result['dialstring'] = result.get('dialstring') or event.skype.replace('\\', '').split(';', 1)[0].replace('conf:', '')

        if getattr(event, 'status', None) == 'CANCELLED':  # CANCELLED|CONFIRMED|....
            result['cancelled'] = True

        return result

    def parse_vcard(self, text):
        result = {}

        if isinstance(text, bytes):
            try:
                text = text.decode('utf-8')
            except UnicodeDecodeError:
                text = text.decode('latin1')

        url = re.search(r'^\s*URL:(.*)$', text, re.MULTILINE)
        if url:
            result['dialstring'] = url.group(1).strip().replace('breeze://', '')

        return result

    def parse_text(self, text, use_fallback_match=False):
        if isinstance(text, bytes):
            try:
                text = text.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    text = text.decode('latin1')
                except UnicodeDecodeError:
                    return {}

        fallback = {}

        # try to find the earliest match
        lines = [l for l in text.strip().split('\n') if l.strip()]

        for i, _line in enumerate(lines):

            cur_text = '\n'.join(lines[i:i + 2])
            match = self._match_text_uris(cur_text, text) or {}

            if match.get('needs_scrape') and ALLOW_SCRAPE:
                # try to guess invite from full content before scrape
                full_regular_match = self._match_text_uris(text.strip(), text.strip())
                if full_regular_match and full_regular_match.get('dialstring'):
                    return full_regular_match

                match = self._match_scraping(cur_text, text) or {}
                match.pop('needs_scrape', None)

            if not match:
                match = self._match_fallback_text(cur_text, text)

            fallback = {**match, **fallback}
            if match.get('dialstring'):
                return match

        if use_fallback_match:
            self.maybe_use_fallback_dialstring(fallback)
        return fallback

    @staticmethod
    def maybe_use_fallback_dialstring(result):

        if result.get('dialstring'):
            return False

        if result.get('dialstring_fallback'):
            result['dialstring'] = result.pop('dialstring_fallback')
            return True

        if result.get('dialstring_fallback_h323'):
            result['dialstring'] = result.pop('dialstring_fallback_h323')
            return True

    def _match_text_uris(self, text: str, full_text: str):
        for fn in [
            self._match_acano_uris,
            self._match_pexip_web_uris,
            self._match_lifesize,
            self._match_bluejeans,
            self._match_webex,
            self._match_zoom,
            self._match_teams,
            self._match_scrape,
        ]:
            try:
                result = fn(text, full_text=full_text)
            except (AttributeError, KeyError):
                if settings.TEST_MODE or settings.DEBUG:
                    raise
                capture_exception()
                continue

            if result:
                return result

    def _match_acano_uris(self, text: str, full_text: str):

        fallback = self._match_fallback_text(full_text) or {}
        fallback_dialstring: str = fallback.get('dialstring') or fallback.get('dialstring_fallback') or ''

        def _acano_result(call_id, domain, webrtc):
            from provider.models.provider import ClusterSettings
            try:
                domain = ClusterSettings.objects.filter(web_domain=domain)\
                             .order_by(F('customer').asc(nulls_last=False)).first().main_domain or domain
            except AttributeError:
                pass

            if fallback_dialstring and fallback_dialstring.startswith(call_id):
                dialstring = fallback_dialstring  # domain is already included as sip uri
            else:
                dialstring = '{}@{}'.format(call_id, domain)

            return {'dialstring': dialstring, 'webrtc': webrtc}

        acano_webrtc_full_match = re.search(r'https://([^/]+)/invited.sf\?([^" >\n]+)', text)
        if acano_webrtc_full_match:
            uri, qs = self._parse_uri(acano_webrtc_full_match.group(0))
            return _acano_result(qs['id'], acano_webrtc_full_match.group(1), acano_webrtc_full_match.group(0))

        acano_webrtc_match = re.search(r'https://([^/]+)/index.html\?(id=(\d+)[^" >\n]*)', text)
        if acano_webrtc_match:
            uri, qs = self._parse_uri(acano_webrtc_match.group(0))
            return _acano_result(qs['id'], acano_webrtc_match.group(1), acano_webrtc_match.group(0))

        acano_webapp_match = re.search(r'https://([^/]+)/meeting/(\d+)([^" >\n]*)', text)
        if acano_webapp_match:
            return _acano_result(acano_webapp_match.group(2), acano_webapp_match.group(1), acano_webapp_match.group(0))

    def _match_pexip_web_uris(self, text: str, full_text: str):

        fallback = self._match_fallback_text(full_text or text) or {}
        fallback_dialstring: str = fallback.get('dialstring') or fallback.get('dialstring_fallback') or ''

        def _pexip_result(alias: str, domain: str, webrtc: str):
            from provider.models.provider import ClusterSettings
            try:
                domain = ClusterSettings.objects.filter(web_domain=domain)\
                             .order_by(F('customer').asc(nulls_last=False)).first().main_domain or domain
            except AttributeError:
                pass

            if '@' not in alias:
                if fallback_dialstring.startswith(alias):
                    alias = fallback_dialstring
                else:
                    alias = '{}@{}'.format(alias, domain)

            return {'dialstring': alias, 'webrtc': webrtc}

        pexip_v25_webapp_match = re.search(r'https://([^/]+)/webapp/?(?:home/)?(?:#/)?\?([^" >\n]*)', text)
        if pexip_v25_webapp_match:
            uri, qs = self._parse_uri(pexip_v25_webapp_match.group(0))
            alias = qs.get('conference') or qs.get('alias') or ''
            if alias:
                return _pexip_result(alias, pexip_v25_webapp_match.group(1), pexip_v25_webapp_match.group(0))

        pexip_v24_webapp_match = re.search(r'https://([^/]+)/webapp/conference/([^/]+)?\?([^" >\n]*)', text)
        if pexip_v24_webapp_match:
            return _pexip_result(pexip_v24_webapp_match.group(2), pexip_v24_webapp_match.group(1), pexip_v24_webapp_match.group(0))

        pexip_teams_match = re.search(r'https://pexip.me/teams/([^/]+)/(\d+)', text)
        if pexip_teams_match:
            return {'dialstring': '{}@{}'.format(pexip_teams_match.group(2), pexip_teams_match.group(1)),
                    'webrtc': pexip_teams_match.group(0)}

    def _match_lifesize(self, text: str, full_text: str):

        try:
            lifesize_match = re.search(r'https://call.lifesizecloud.com/(\d+)', text)
            return {'dialstring': '{}@sip.lifesizecloud.com'.format(lifesize_match.group(1)),
                    'webrtc': lifesize_match.group(0)}
        except AttributeError:
            pass

    def _match_zoom(self, text: str, full_text: str):

        try:
            zoom_match = re.search(r'(\d+)((?:\.\d+){0,3})@(zoomcrc.com)', text)

            webrtc_match = re.search(r'https://[A-z0-9-]+\.zoom.us/j/[^" <]+', full_text or text)

            suffix = ''
            webrtc = ''
            if '.' not in zoom_match.group(2) and 'Passcode:' in full_text:
                passcode_match = re.search(r'Passcode: (\d+)', full_text)
                if not passcode_match:
                    passcode_match = re.search(r',,\*(\d+)#', full_text)

                if passcode_match:
                    suffix = '.' + passcode_match.group(1)
                    host_key_match = re.search(r'Host [Kk]ey: (\d+)', full_text)
                    if host_key_match:
                        suffix += '..' + host_key_match.group(0)

            if webrtc_match and zoom_match.group(1) in webrtc_match.group(0):
                webrtc = webrtc_match.group(0)

            return {'dialstring': '{}{}@{}'.format(zoom_match.group(1), suffix, zoom_match.group(3)),
                    'webrtc': webrtc}
        except AttributeError:
            pass

    def _match_bluejeans(self, text: str, full_text: str):

        try:
            bluejeans_match = re.search(r'https://bluejeans.com/(\d+)(\.\d+)?', text or '')
            return {'dialstring': '{}{}@bjn.vc'.format(bluejeans_match.group(1), bluejeans_match.group(2) or ''),
                    'webrtc': bluejeans_match.group(0)}
        except AttributeError:
            pass

        try:
            bluejeans_teams_match = re.search(r'Join with a video conferencing device\s+(\d+)@teams.bjn.vc.*?VTC Conference ID: (\d+)', text or '')
            return {'dialstring': '{}.{}@teams.bjn.vc'.format(bluejeans_teams_match.group(1), bluejeans_teams_match.group(2))}
        except AttributeError:
            pass

    def _match_teams(self, text: str, full_text: str):

        teams_webrtc = None
        try:
            teams_webrtc_match = re.search(r'https://teams.microsoft.com/l/meetup-join/[^" \n>"]+', text or '')
            teams_webrtc = {
                'dialstring_webrtc': teams_webrtc_match.group(0),
                'webrtc': teams_webrtc_match.group(0),
            }
        except AttributeError:
            pass

        # pexip cvi
        try:
            other_teams = re.search(r'https://[^/]+/teams/\?([^ \n>"]+)', full_text or text or '')
            try:
                uri, qs = self._parse_uri(other_teams.group(0))
            except ValueError:
                pass
            else:
                return {
                    'dialstring': '{}{}@{}'.format(qs.get('prefix') or '', qs['conf'], qs['d']),
                    'dialstring_fallback_h323': '{}@{}'.format(qs['conf'], qs['ip']) if qs.get('ip') else '',
                    **(teams_webrtc or {}),
                }
        except (AttributeError, KeyError):
            pass

        if teams_webrtc:  # no sip, return just teams_webrtc
            return teams_webrtc

    def _match_webex(self, text: str, full_text: str):

        try:
            webex__teams_url_match = re.search(r'https://([^.]+).webex.com/msteams/?\?([^"?/ \n<>]+)', text or '')
            if webex__teams_url_match:
                uri, qs = self._parse_uri(webex__teams_url_match.group(0))
                if qs.get('confid') and qs.get('domain'):
                    suffix = '.{}'.format(qs['tenantkey']) if qs.get('tenantkey') else ''
                    dialstring = '{}{}@{}'.format(qs['confid'], suffix, qs['domain'])

                    teams_match = self._match_teams(text, full_text) or {}
                    return {'dialstring': dialstring, 'webrtc': teams_match.get('webrtc') or uri}
        except (ValueError, AttributeError):
            pass

        try:
            webex_url_match = re.search(r'https://([^.]+).webex.com/meet/([^"?/ \n<>]+)', text or '')
            return {'dialstring': '{}@{}.webex.com'.format(webex_url_match.group(2), webex_url_match.group(1)),
                    'webrtc': webex_url_match.group(0)}
        except AttributeError:
            pass

        try:
            webex_code_code_join_url = re.search(
                r'access code\): ([\d ]+)[\n ]*Join<(https://([^".]+)\.webex.com/join/[^?/ \n<>]+)', text or '', re.DOTALL)
            return {'dialstring': '{}.{}@webex.com'.format(webex_code_code_join_url.group(1).replace(' ', ''), webex_code_code_join_url.group(3)),
                    'webrtc': webex_code_code_join_url.group(2)}
        except AttributeError:
            pass

        try:
            webex_code_other_join_url = re.search(
                r'access code\): ([\d ]+).+(https://([^\.]+).webex.com/([^".]+)/j.php?MTID=([^?/ \n<>]+))', text or '', re.DOTALL)

            return {'dialstring': '{}.{}@webex.com'.format(webex_code_other_join_url.group(1).replace(' ', ''), webex_code_other_join_url.group(3)),
                    'webrtc': webex_code_other_join_url.group(2)}
        except AttributeError:
            pass

        try:
            webex_lync_match = re.search(r'(?:^|[ <])([A-z0-9._]+)\.([^@]+).lync.webex.com', text or '')
            return {'dialstring': '{}@{}.webex.com'.format(webex_lync_match.group(1), webex_lync_match.group(2))}
        except AttributeError:
            pass

    def _match_skype_conference_id(self, text: str, full_text: str):

        m = re.search(r'[-]ID: (\d+)\n', full_text)
        if m:
            return {'skype_conference_id': m.group(1)}

    def _match_scrape(self, text: str, full_text: str):
        needs_scrape = (
            re.search(r'https://meet.starleaf.com/(\d+)', text) or
            re.search(r'https://([^\.]+)\.webex.com/join/([^?/ \n<>]+)', text or '') or
            re.search(r'https://([^\.]+).webex.com/([^\.]+)/j.php?MTID=([^?/ \n<>]+)', text or '')
        )
        if needs_scrape:
            return {'needs_scrape': True}

    def _cached(self, url: str, callback: Callable[[], Optional[Dict]]):
        cache_key = 'calendar.dialstring.{}'.format(md5(force_bytes(url)).hexdigest())
        undef = object()
        cached = cache.get(cache_key, undef)
        if cached is not undef:
            return cached

        result = callback()
        cache.set(cache_key, result, 7 * 24 * 60 * 60)
        return result

    def _match_scraping(self, text: str, full_text: str):

        try:
            starleaf_match = re.search(r'https://meet.starleaf.com/(\d+)', text)
            return self._cached(starleaf_match.group(0),
                                lambda: self.fetch_starleaf_url(starleaf_match.group(1))
                                )
        except AttributeError:
            pass

        try:
            webex_personal_join_url = re.search(
                r'https://([^\.]+)\.webex.com/join/([^"?/ \n<>]+)', text or '')
            result = self._cached(webex_personal_join_url.group(0),
                                  lambda: self.fetch_cisco_personal_url(webex_personal_join_url.group(1),
                                                                        webex_personal_join_url.group(2))
                                  )
            if result:
                return result
        except AttributeError:
            pass
        try:
            webex_other_join_url = re.search(
                r'https://([^\.]+).webex.com/([^\.]+)/j.php?MTID=([^"?/ \n<>]+)', text or '')

            result = self._cached(webex_other_join_url.group(0),
                                  lambda: self.fetch_cisco_scheduled_url(webex_other_join_url.group(1),
                                                                         webex_other_join_url.group(2),
                                                                         webex_other_join_url.group(3))
                                  )
            if result:
                return result
        except AttributeError:
            pass

    def _match_fallback_text(self, text: str, full_text: str = None):

        sip_adresses = re.findall(r'(?:sip|s4b|lync):([A-z0-9-_\.@]+)', text, re.IGNORECASE)
        sip_adresses += re.findall(r'(?:^|[\s"]|mailto:)(\d+@[^.]+\.call.sl)', text)  # starleaf

        if sip_adresses:
            return {'dialstring': sip_adresses[0].strip('.')}

        try:
            numeric_fallback_match = re.search(r'(?:^|[>"\s]|mailto:)(\d\d\d+@[A-z0-9\.-]+\.[A-z0-9]{1,5})', text, re.MULTILINE)

            return {'dialstring_fallback': numeric_fallback_match.group(1)}
        except AttributeError:
            pass

        try:
            text_fallback_match = re.search(r'(?:^|[>"\s]|mailto:)([A-z0-9\.]+\.(vr|vmr|cospace|space)@[A-z0-9\.-]+\.[A-z0-9]{1,5})', text, re.MULTILINE)

            return {'dialstring_fallback': text_fallback_match.group(1)}
        except AttributeError:
            pass

        try:
            h323_fallback_match = re.search(r'(?:^|[>"\s])([A-z0-9\.-]+\.[A-z0-9]{1,5}##(\d+)(#\d+)?)', text)
            return {'dialstring_fallback_h323': h323_fallback_match.group(1)}
        except AttributeError:
            pass

        return {}

    def fetch_cisco_personal_url(self, site, username):
        import requests
        response = requests.get('https://{}.webex.com/webappng/api/v1/pmr/{}/view?siteurl={}'.format(site, site, username))
        if response.status_code != 200:
            return

        try:
            data = response.json()
        except (KeyError, ValueError):
            pass
        else:
            if data.get('meetingNumber'):
                return {'dialstring': '{}.{}@webex.com'.format(data['meetingNumber'], site)}

    def fetch_cisco_scheduled_url(self, site, site2, mt_id):
        import requests

        session = requests.Session()
        response = session.get('https://{}.webex.com/{}/j.php?MTID={}'.format(site, site, mt_id))
        if response.status_code != 200:
            return

        try:
            meeting_id = re.search(r'/meeting/info/(\d+)', response.url).group(1)
        except AttributeError:
            return

        response = session.get('https://{}.webex.com/webappng/api/v1/meetings/{}?MTID={}&siteurl={}'.format(site,  meeting_id, mt_id, site2))
        if response.status_code != 200:
            return
        try:
            data = response.json()
        except (KeyError, ValueError):
            pass
        else:
            if data.get('meetingKey'):
                return {'dialstring': '{}.{}@webex.com'.format(data['meetingKey'], site)}

    def fetch_starleaf_url(self, call_id):
        # TODO cache
        import requests
        response = requests.get('https://meet.starleaf.com/v1/webrtc/org_domain?target={}'.format(call_id))
        if response.status_code == 200:

            try:
                data = response.json()
            except ValueError:
                pass
            else:
                if data.get('org_domain'):
                    return {'dialstring': '{}@{}'.format(call_id, data['org_domain'])}

        data = '<?xml version="1.0"?><methodCall><methodName>getCallInfoByConfDN</methodName><params><param><value><nil></nil></value></param><param><value><string>{}</string></value></param></params></methodCall>'.format(call_id)


        response = requests.post('https://meet.starleaf.com/RPC2', data, headers={'Content-Type': 'text/xml'})

        if response.status_code == 200:
            sip_match = re.search(r'{}@[^\.]\.call.sl'.format(call_id), response.text)
            h323_match = re.search(r'\d+\.\d+\.\d+\.\d+##{}'.format(call_id), response.text)

            result = {}
            if sip_match:
                result['dialstring'] = sip_match.group(0)
            if h323_match:
                result['dialstring_fallback_h323'] = h323_match.group(0)

            return result

    def _parse_uri(self, uri: str):
        """
        Parse possibly encoded url
        """
        try:
            uri = html.unescape(uri)
        except ValueError:
            uri = uri.replace('&amp;', '&')

        if '?' in uri:
            return uri, dict(parse_qsl(uri.split('?', 1)[1]))

        pass  # Here used to be unquote(uri) to get %0f as characters. Are urls ever double quoted in invites?

        try:
            return uri, dict(parse_qsl(uri))
        except (AttributeError, ValueError):
            pass

        return uri, {}


def fix_subject(subject: str) -> str:
    """
    Removes RE: RE: Fwd: etc
    """
    PREFIX = re.compile(r'^(Vb|Fw|Fwd|Re|Sv|SV|Inbjudan|Invite): ?', re.IGNORECASE)

    while True:
        match = PREFIX.match(subject)
        if not match:
            return subject
        subject = subject[len(match.group(0)):].strip()
