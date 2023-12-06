from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from descriptive_choices import DescriptiveChoices

ENABLE_LIFESIZE_MESSAGES = getattr(settings, 'ENABLE_LIFESIZE_MESSAGES', False)

ADD_CUSTOM_MESSAGE_TYPES = getattr(settings, 'ADD_CUSTOM_MESSAGE_TYPES', ())

if any(c[0] < 100 for c in ADD_CUSTOM_MESSAGE_TYPES):
    raise ValueError('ADD_CUSTOM_MESSAGE_TYPES needs to have ids >= 100')

TYPE_CHOICES = [
    (0, 'outlook_welcome', _('Outlook-meddelande'), _('''Meddelande som visas i plugin''')),
]

if ENABLE_LIFESIZE_MESSAGES:
    TYPE_CHOICES += [
        (1, 'lifesize_meeting', _('Interna tvåpartsmöten'), _('''Innehåll i e-postmeddelande för möten som sker direkt mellan systemen''')),
        (3, 'lifesize_meeting_pin', _('Interna möten med PIN-kod'), _('''Innehåll i e-postmeddelande för möten skulle kunnat ske direkt mellan systemen, men kräver en port på bryggan pga PIN''')),
        (4, 'lifesize_multipart', _('Interna möten utan PIN-kod'), _('''Innehåll i e-postmeddelande för flerpartsmöten som inte tillåter clearsea-användare''')),
    ]
TYPE_CHOICES += [
    (
        2,
        'clearsea_meeting',
        _('Flerpartsmöten i VMR'),
        _('''Inbjudan för bokade flerpartsmöten i tillfälliga virtuella mötesrum, utan PIN-kod'''),
    ),
    (
        5,
        'clearsea_meeting_pin',
        _('Flerpartsmöten med PIN-kod'),
        _('''Inbjudan för bokade flerpartsmöten i tillfälliga virtuella mötesrum med PIN-kod'''),
    ),
    (
        12,
        'clearsea_meeting_pin_moderator',
        _('Moderator flerpartsmöten med PIN-kod'),
        _(
            '''Inbjudan för moderatorer i bokade flerpartsmöten i tillfälliga virtuella mötesrum med PIN-kod'''
        ),
    ),
]

MAKESPACE_MESSAGES = [
    (6, 'acano_cospace', _('Inbjudan statiskt mötesrum'), _('''Anslutningsinformation till statiska mötesrum''')),
    (10, 'acano_user', _('Instruktioner till användare'), _('''Anslutningsinformation till en användares och dess mötesrum''')),
    (7, 'acano_client', _('Inbjudan CMA/WebRTC-klient'), _('''Anslutningsinformation som skickas ut från CMA/WebRTC''')),
]

TYPE_CHOICES += MAKESPACE_MESSAGES + [
    (8, 'webinar_moderator', _('Inbjudan som moderator i webinar'), _('''Inbjudan till moderatorer för tillfälliga webinar''')),
    (9, 'webinar', _('Inbjudan till webinar'), _('''Inbjudan till gästdeltagare för tillfälliga webinar''')),
    (11, 'sandbox', _('Testmeddelande'), _('''Testa dina meddelandekoder utan att de påverkar slutanvändare''')),
]

DEFAULT_PATIENT_MESSAGES = [
    (100, 'individual_planning_moderator', ('Inbjudan som moderator i SIP'), _('''Inbjudan till moderatorer av videobaserade SIP-möten''')),
    (101, 'individual_planning', ('Inbjudan till SIP-patient'), _('''Inbjudan till patienter/gästanvändare i videobaserade SIP-möten''')),

    (102, 'medic_care_moderator', ('Inbjudan som moderator vårdmöte'), _('''Inbjudan till moderatorer av videobaserade vårdmöten''')),
    (103, 'medic_care', ('Inbjudan till patient, vårdmöte'), _('''Inbjudan till patienter/gästanvändare i videobaserade vårdmöten''')),
]

if settings.ENABLE_PATIENT_MESSAGES:
    TYPE_CHOICES += DEFAULT_PATIENT_MESSAGES

if ADD_CUSTOM_MESSAGE_TYPES:
    TYPE_CHOICES += list(ADD_CUSTOM_MESSAGE_TYPES)


def get_enabled_types():
    result = TYPE_CHOICES
    if getattr(settings, 'ONLY_MAKESPACE_MESSAGES', False):
        result = DescriptiveChoices(MAKESPACE_MESSAGES)
    if not settings.ENABLE_OLD_OUTLOOK_PLUGIN:
        result = [r for r in result if r[1] != 'outlook_welcome']

    return DescriptiveChoices(result)


ENABLED_TYPES = get_enabled_types()


TYPES = DescriptiveChoices(TYPE_CHOICES)

PLAIN_TEXT_TYPES = [
    TYPES.acano_client,
]

PUBLIC_URL_TYPES = [
    TYPES.acano_client,
]

ATTACHMENT_TYPES = [
    TYPES.acano_cospace,
    TYPES.acano_user,
]
