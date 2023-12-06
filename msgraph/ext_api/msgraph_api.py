from typing import TYPE_CHECKING, List

from django.core import validators

from provider.exceptions import AuthenticationError, ResponseError, NotFound, ResponseConnectionError
from provider.ext_api.base import RestProviderAPI
from provider.types import ProviderAPICompatible

if TYPE_CHECKING:
    from msgraph.models import MSGraphCredentials


class MSGraphAPI(RestProviderAPI):

    has_place_scope = None
    provider: 'MSGraphCredentials'
    scopes: List[str]

    def __init__(self, provider: ProviderAPICompatible, customer=None, allow_cached_values=None):
        super().__init__(provider, customer, allow_cached_values)

        self.scopes = []
        if self.provider.oauth_credential_id and self.provider.oauth_credential.access_token:
            scopes = self.provider.oauth_credential.access_token.get('scope') or []
            if isinstance(scopes, list):
                self.scopes = scopes

            if any('Place.Read' in scope for scope in scopes):
                self.has_place_scope = True

    def get_session(self):
        if not self.provider.oauth_credential_id:
            raise AuthenticationError('Graph connection has no OAuth connection')
        return self.provider.oauth_credential.session

    def login(self, force=False):
        if not self.provider.oauth_credential_id:
            if force:
                raise AuthenticationError('No valid session')
            return
        if force:
            self.provider.oauth_credential.fetch_token()  # TODO raise error instead?
        self.provider.oauth_credential.check_session()
        return bool(self.provider.oauth_credential.access_token)

    def get_value(self, url, params=None, **kwargs):
        if params is not None:
            kwargs['params'] = params
        response = self.get(url, **kwargs)
        return response.json()['value']

    def check_response_errors(self, response):
        super().check_response_errors(response)

        if response.status_code == 401:
            raise AuthenticationError('Authentication error', response)

        if response.status_code == 404:
            raise NotFound('Not found', response)

        if not str(response.status_code).startswith('2'):
            if '"message"' in response.text:
                try:
                    message = response.json().get('error', {}).get('message')
                except Exception:
                    pass
                else:
                    raise ResponseError(message, response)
            if response.status_code in (503, 504):
                raise ResponseConnectionError('Connection error', response)
            raise ResponseError('Response error', response)

    def get_base_url(self):
        return 'https://graph.microsoft.com/v1.0'

    def get_me(self):
        try:
            response = self.get('me')
        except NotFound:
            return None
        data = response.json()
        return data.get('userPrincipalName') or data.get('mail') or None

    def get_room_lists(self, has_place_scope=None):

        if has_place_scope is None:
            has_place_scope = self.has_place_scope

        try:
            if has_place_scope is not False:
                return self.get_room_lists_using_places()
        except AuthenticationError:
            if has_place_scope:
                raise
            self.has_place_scope = False

        return self.get_room_lists_using_user()

    def get_room_lists_using_places(self):
        return self.get_value('places/microsoft.graph.roomlist')

    def get_room_lists_using_user(self):
        try:
            return self.get_value('beta/me/findRoomLists')
        except ResponseError as e:
            if e.args and 'Resource not found for the segment ' in e.args[0]:
                raise AuthenticationError('Place.Read.All or User.Read.All permission is required', e.args[1])
            raise

    def get_rooms(self, room_list_address=None, has_place_scope=None):

        if room_list_address:
            validators.validate_email(room_list_address)

        if has_place_scope is None:
            has_place_scope = self.has_place_scope

        try:
            if has_place_scope is not False:
                return self.get_rooms_using_places(room_list_address)
        except AuthenticationError:
            if has_place_scope:
                raise
            self.has_place_scope = False

        return self.get_rooms_using_user(room_list_address)

    def get_rooms_using_places(self, room_list_address=None):
        if not room_list_address:
            return self.get_value('places/microsoft.graph.room')
        return self.get_value('places/{}/microsoft.graph.roomlist/rooms'.format(room_list_address))

    def get_rooms_using_user(self, room_list_address=None):
        try:
            if not room_list_address:
                return self.get_value('beta/me/findRooms')
            return self.get_value("beta/me/findRooms(RoomList='{}')".format(room_list_address))
        except ResponseError as e:
            if e.args and 'Resource not found for the segment ' in e.args[0]:
                raise AuthenticationError('Place.Read.All or User.Read.All permission is required', e.args[1])
            raise

    def calendar_view(self, room_list_address, ts_start, ts_stop):
        if room_list_address != 'me':
            validators.validate_email(room_list_address)

        PAGE_SIZE = 500

        params = {
            'startDateTime': ts_start.isoformat(),
            'endDateTime': ts_stop.isoformat(),
            '$count': 'true',
            '$orderby': 'iCalUId',
            '$top': PAGE_SIZE,
            # '$expand': 'singleValueExtendedProperties($filter=id eq \'mividas_meeting_id\')',
        }

        result = []
        for i in range(int(10000 / PAGE_SIZE)):
            params['$skip'] = i * PAGE_SIZE
            response = self.get('users/{}/calendar/calendarView'.format(room_list_address), params=params)
            data = response.json()
            result.extend(data['value'])
            if len(data['value']) < PAGE_SIZE or len(result) < params.get('@odata.count', 0):
                break

        return result

    def parse_recurring(self):
        """
        if 'type' == 'Daily': {
                addRule(rrule, "FREQ", "DAILY");
                setInterval(oPattern.Interval);


        if 'type' == 'Weekly': {
                addRule(rrule, "FREQ", "WEEKLY");
                setInterval(oPattern.Interval);
                if ((oPattern.DayOfWeekMask & (oPattern.DayOfWeekMask-1)) != 0) { //is not a power of 2 (i.e. not just a single day)
                    // Need to work out "BY" pattern
                    // Eg "BYDAY=MO,TU,WE,TH,FR"
                    addRule(rrule, "BYDAY", string.Join(",", getByDay(oPattern.DayOfWeekMask).ToArray()));


        if 'type' == 'Monthly': {
                addRule(rrule, "FREQ", "MONTHLY");
                setInterval(oPattern.Interval);
                //Outlook runs on last day of month if day doesn't exist; Google doesn't run at all - so fix
                if (oPattern.PatternStartDate.Day > 28) {
                    addRule(rrule, "BYDAY", "SU,MO,TU,WE,TH,FR,SA");
                    addRule(rrule, "BYSETPOS", "-1");


        if 'type' == 'MonthNth': {
                addRule(rrule, "FREQ", "MONTHLY");
                setInterval(oPattern.Interval);
                addRule(rrule, "BYDAY", string.Join(",", getByDay(oPattern.DayOfWeekMask).ToArray()));
                addRule(rrule, "BYSETPOS", (oPattern.Instance == 5) ? "-1" : oPattern.Instance.ToString());

        if 'type' == 'Yearly': {
                addRule(rrule, "FREQ", "YEARLY");
                //Google interval is years, Outlook is months
                if (oPattern.Interval != 12)
                    addRule(rrule, "INTERVAL", (oPattern.Interval / 12).ToString());

        if 'type' == 'YearNth': {
                //Issue 445: Outlook incorrectly surfaces 12 monthly recurrences as olRecursYearNth, so we'll undo that.
                //In addition, many apps, indeed even the Google webapp, doesn't display a yearly recurrence rule properly
                //despite actually showing the events on the right dates.
                //So to make OGCS work better with apps that aren't providing full iCal functionality, we'll translate this
                //into a monthly recurrence instead.
                addRule(rrule, "FREQ", "MONTHLY");
                addRule(rrule, "INTERVAL", oPattern.Interval.ToString());

                /*Strictly, what we /should/ be doing is:
                addRule(rrule, "FREQ", "YEARLY");
                if (oPattern.Interval != 12)
                    addRule(rrule, "INTERVAL", (oPattern.Interval / 12).ToString());
                addRule(rrule, "BYMONTH", oPattern.MonthOfYear.ToString());
                */
                if (oPattern.DayOfWeekMask != (OlDaysOfWeek)127) { //If not every day of week, define which ones
                    addRule(rrule, "BYDAY", string.Join(",", getByDay(oPattern.DayOfWeekMask).ToArray()));

                addRule(rrule, "BYSETPOS", (oPattern.Instance == 5) ? "-1" : oPattern.Instance.ToString());

"""
