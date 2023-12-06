import { $gettext } from '@/vue/helpers/translate'

export const endpointStatusNames = {
    '-10': $gettext('Inte accepterad'),
    '-2': $gettext('Anslutningsfel'),
    '-1': $gettext('Inloggningsfel'),
    0: 'Offline',
    1: $gettext('Okänd'),
    10: 'Online',
    20: $gettext('I samtal'),
}

export const endpointStatusChoices = Object.entries(endpointStatusNames).map(s => ({ id: parseInt(s[0], 10), title: s[1] }))

export const endpointConnectionTypeNames = {
    0: $gettext('Passiv, bakom brandvägg'),
    1: $gettext('Direktanslutning'),
    2: $gettext('Proxy'),
}

export const endpointConnectionTypeChoices = Object.entries(endpointConnectionTypeNames).map(s => ({ id: parseInt(s[0], 10), title: s[1] }))

export const peopleStatusNames = {
    offline: {
        title: $gettext('Offline'),
        icon: 'mdi-circle-outline'
    },
    err: {
        title: $gettext('Något fel'),
        icon: 'mdi-alert'
    },
    free: {
        title: $gettext('Ledigt'),
        icon: 'mdi-circle'
    },
    call: {
        title: $gettext('I samtal'),
        icon: 'mdi-phone-in-talk'
    },
    meeting: {
        title: $gettext('Bokat möte'),
        icon: 'mdi-calendar-blank'
    },
    meeting_participants: {
        title: $gettext('Bokat möte'),
        icon: 'mdi-calendar-account'
    },
    ghost: {
        title: $gettext('Ghost meeting'),
        icon: 'mdi-ghost'
    },
    adhoc: {
        title: $gettext('Adhoc'),
        icon: 'mdi-calendar-account'
    },
    occupied: {
        title: $gettext('Möte'),
        icon: 'mdi-account-multiple'
    }
}

export const endpointTaskTypeNames = {
    'configuration': $gettext('Konfiguration'),
    'template': $gettext('Mall'),
    'commands': $gettext('Kommando'),
    'dial_info': $gettext('Uppringningsegenskaper'),
    'backup': $gettext('Backup'),
    'events': $gettext('Event'),
    'branding': $gettext('Branding'),
    'room_analytics': $gettext('Rumsanalys'),
    'repeat': $gettext('Repetera åtgärd'),
    'password': $gettext('Lösenord'),
    'passive': $gettext('Passiv'),
    'statistics': $gettext('Statistik'),
    'address_book': $gettext('Adressbok'),
    'room_controls': $gettext('Rumskontroll'),
    'room_controls_restart': $gettext('Rumskontroll'),
    'firmware': $gettext('Firmware'),
    'create': $gettext('Skapad'),
    'update': $gettext('Uppdaterad'),
    'delete': $gettext('Raderad'),
}

export const endpointTaskTypeChoices = Object.entries(endpointTaskTypeNames).map(s => ({ id: s[0], title: s[1] }))

export const endpointTaskStatusNames = {
    '-10': $gettext('Fel'),
    '-1': $gettext('Avbruten'),
    '0': $gettext('Väntar'),
    '5': $gettext('I kö'),
    '10': $gettext('Avklarad'),
}

export const endpointTaskStatusChoices = Object.entries(endpointTaskStatusNames).map(s => ({ id: parseInt(s[0], 10), title: s[1] }))

export const endpointModelFamilies = {
    's52030': 'SX10',
    's52010': 'SX20, MX200 G2, MX300 G2, MX200 G2, MX300 G2',
    's52011': 'SX20',
    's52020': 'SX80, MX700, MX800, MX800 Dual',
    's52040': 'DX80, DX70',
    's53200': 'Room Series, Board Series, Room 55/70',
    's53300': 'Room Kit Pro, Room 70 G2, Panorama, Desk Series',
}

export const EndpointManufacturer = {
    cisco: 10,
    poly_trio: 20,
    poly_studiox: 21,
    poly_group: 22,
    poly_hdx: 23,
    poly_other: 90,
}

export const endpointManufacturerNames = {
    [EndpointManufacturer.cisco]: $gettext('Cisco system'),
    [EndpointManufacturer.poly_trio]: $gettext('Poly Trio'),
    [EndpointManufacturer.poly_studiox]: $gettext('Poly Studio X-series'),
    [EndpointManufacturer.poly_group]: $gettext('Poly Group'),
    [EndpointManufacturer.poly_hdx]: $gettext('Poly HDX'),
    [EndpointManufacturer.poly_other]: $gettext('Other'),
}

export const endpointManufacturerChoices = Object.entries(endpointManufacturerNames).map(s => ({ id: parseInt(s[0], 10), title: s[1] }))

export const PLACEHOLDER_PASSWORD = '_***_'
