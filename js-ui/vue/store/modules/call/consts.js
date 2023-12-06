import { $gettext } from '@/vue/helpers/translate'

export const callLayoutTypes = {
    automatic: $gettext('Automatisk'),
    allEqual: $gettext('Dela utrymme mellan deltagare'),
    speakerOnly: $gettext('Endast talare'),
    telepresence: $gettext('Talare med övriga deltagare flytande'),
    stacked: $gettext('Talare med övriga deltagare under')
}

export const callLayoutChoices = Object.entries(callLayoutTypes).map(s => ({ id: s[0], title: s[1] }))

export const pexipCallModeTypes = {
    'audio': $gettext('Bara ljud'),
    'video': $gettext('Huvudvideo + presentation'),
    'video-only': $gettext('Bara huvudvideo'),
    'streaming': $gettext('Streaming'),
}

export const pexipCallModeChoices = Object.entries(pexipCallModeTypes).map(s => ({ id: s[0], title: s[1] }))
