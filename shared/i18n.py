from django.utils.translation import ngettext

# define plural strings which only exists as single in python code

def _strings():
    ngettext('Kund', 'Kunder', 1)
    ngettext('Kluster', 'Kluster', 1)
    ngettext('Mötesrum', 'Mötesrum', 1)
    ngettext('System', 'System', 1)
    ngettext('Rum', 'Rum', 1)
