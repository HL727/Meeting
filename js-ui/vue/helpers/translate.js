import { translate } from 'vue-gettext'
import '@/vue/i18n'

const $gettext = translate.gettext
const $ngettext = translate.ngettext

const $gettextInterpolate = translate.gettextInterpolate || function(...args) {
    if (window.MIVIDAS && window.MIVIDAS.$gettextInterpolate) {
        return window.MIVIDAS.$gettextInterpolate.apply(this, args)
    }
    return args[0]
}

export {
    translate,
    $gettext,
    $ngettext,
    $gettextInterpolate,
}
