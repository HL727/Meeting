import { $gettext, $ngettext } from '@/vue/helpers/translate'

export const pexipCospaceTypes = {
    'conference': $ngettext('Mötesrum', 'Mötesrum', 1),
    'lecture': $gettext('Webinar'),
    'test_call': $gettext('Testmöte'),
}

export const pexipCospaceChoices = Object.entries(pexipCospaceTypes).map(s => ({ id: s[0], title: s[1] }))

export const pexipCospaceFilterTypes = {
    'cospace': $ngettext('Mötesrum', 'Mötesrum', 1),
    'webinar': $gettext('Webinar'),
}

export const pexipGuestLayouts = {
    one_main_zero_pips: 'Full-screen main speaker only',
    one_main_seven_pips: 'Large main speaker and up to 7 other participants',
    one_main_twentyone_pips: 'Main speaker and up to 21 other participants',
    two_mains_twentyone_pips: 'Two main speakers and up to 21 other participants',
    four_mains_zero_pips: 'Up to four main speakers, with no thumbnails',
}

export const pexipGuestLayoutChoices = Object.entries(pexipGuestLayouts).map(s => ({ id: s[0], title: s[1] }))

export const pexipHostLayouts = {
    one_main_zero_pips: 'Full-screen main speaker only',
    one_main_seven_pips: 'Large main speaker and up to 7 other participants',
    one_main_twentyone_pips: 'Main speaker and up to 21 other participants',
    two_mains_twentyone_pips: 'Two main speakers and up to 21 other participants',
    four_mains_zero_pips: 'Up to four main speakers, with no thumbnails',
    five_mains_seven_pips: 'Adaptive Composition layout (does not apply to service_type of lecture)',

}
export const pexipHostLayoutChoices = Object.entries(pexipHostLayouts).map(s => ({ id: s[0], title: s[1] }))
