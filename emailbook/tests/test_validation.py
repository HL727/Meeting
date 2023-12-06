from django.utils.translation import ugettext as _

from calendar_invite.tests import _get_full_message
from conferencecenter.tests.base import ConferenceBaseTest
from emailbook.handler import EmailHandler


class ValidationTestCase(ConferenceBaseTest):

    def setUp(self):
        self._init()

    def test_invalid_time(self):

        handler = EmailHandler(_get_full_message(calendar=False).as_string())
        valid, content, error = handler.validate()

        self.assertEqual(error, _('Kunde inte hitta något möte. Vänligen kontrollera att kalenderbokning skickats med som bilaga till meddelandet'))

    def test_valid(self):
        handler = EmailHandler(_get_full_message().as_string())
        valid, content, error = handler.validate()

        self.assertEqual(error, '')
        self.assertEqual(valid, True)
