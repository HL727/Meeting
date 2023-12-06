from collections import namedtuple
from django.utils.translation import ugettext as _

standard_message = _('''
<p><strong><u>För deltagare med videokonferenssystem, Lync eller Skype for Business</u></strong></p>
<p>Ange adressen (dial string) {sip_numeric}. {if password}Mötets PIN-kod är: {password}. Avsluta med #{endif}</p>
<p><a title="Direktlänk S4B/Lync" href="sip:{sip_numeric}">Direktlänk S4B/Lync</a></p>
<p><u><strong>För deltagande via dator eller annan mobil enhet</strong></u><br />Klicka på länken och följ instruktionerna {web_link}</p>
<p><strong><u>För deltagagande per telefon (dvs. endast ljud)</u></strong><br />Ring {phone_ivr} och ange mötes-ID {room_number}. Avsluta med #. {if password}Mötets PIN-kod är: {password}. Avsluta med #{endif}</p>
<p> </p>
{if logo}<p>{logo}</p>{endif}
''').strip()


secure_standard_message = _(
    '''
<p><strong>För deltagare via webbläsare/mobil</strong></p>
<p>Anslut till mötet genom att klicka på "Anslut via webbläsare"-knappen</p>
<p><strong>För deltagare video videokonferenssystem</strong></p>
<p>Anslut till mötet genom att aktivera anslutning via SIP, om mötet har stöd för det</p>
'''
).strip()


MessageTuple = namedtuple('MessageTuple', 'name value')

INITIAL_MESSAGES = [
    MessageTuple._make(m)
    for m in {
        'clearsea_meeting': {
            'title': _('Du är inbjuden till ett videomöte'),
            'content': standard_message,
        },
        'clearsea_meeting_pin': {
            'title': _('Du är inbjuden till ett videomöte'),
            'content': standard_message,
        },
        'clearsea_meeting_pin_moderator': {
            'title': _('Du är inbjuden till att moderera ett videomöte'),
            'content': standard_message,
        },
        'acano_cospace': {
            'title': _('Anslutningsinformation till {title}'),
            'content': standard_message,
        },
        'acano_user': {
            'title': _('Anslutningsuppgifter till ditt videomötesrum'),
            'content': _(
                '''
<p><u>Ditt användarnamn är</u> <strong><u>{owner}</u></strong></p>
<p><strong><u>För deltagare med videokonferenssystem, Lync eller Skype for Business</u></strong></p>
<p>Ange adressen (dial string) {sip_numeric}. {if password}Mötets PIN-kod är: {password}. Avsluta med #{endif} </p>
<p><a title="Direktlänk S4B/Lync" href="sip:{sip_numeric}">Direktlänk S4B/Lync</a></p>
<p><u><strong>För deltagande via dator eller annan mobil enhet</strong></u><br />Klicka på länken och följ instruktionerna {web_link}</p>
<p><strong><u>För deltagagande per telefon (dvs. endast ljud)</u></strong><br />Ring {phone_ivr} och ange mötes-ID {room_number}. Avsluta med #. {if password}Mötets PIN-kod är: {password}. Avsluta med #{endif}</p>
<p> </p>
{if logo}<p>{logo}</p>{endif}
        '''
            ).strip(),
        },
        'webinar_moderator': {
            'title': _('Du är inbjuden som moderator till ett webinar'),
            'content': standard_message,
        },
        'webinar': {
            'title': _('Du är inbjuden att delta i ett webinar'),
            'content': standard_message,
        },
        'individual_planning_moderator': {
            'title': _('Du är inbjuden som moderator i ett videobaserat SIP-möte'),
            'content': standard_message,
        },
        'individual_planning': {
            'title': _('Du är inbjuden att delta i ett videobaserat SIP-möte'),
            'content': standard_message,
        },
        'medic_care_moderator': {
            'title': _('Du är inbjuden som moderator i ett videobaserat patientmöte'),
            'content': standard_message,
        },
        'medic_care': {
            'title': _('Du är inbjuden att delta i ett videobaserat patientmöte'),
            'content': standard_message,
        },
        'secure': {
            'title': _('Du är inbjuden till ett säkert videomöte'),
            'content': secure_standard_message,
        },
        'secure_moderator': {
            'title': _('Du är inbjuden att moderera säkert videomöte'),
            'content': secure_standard_message,
        },
        'sandbox': {
            'title': _('Testmeddelande, debug'),
            'content': 'dynamic',  # overridden when populating
        },
    }.items()
]
