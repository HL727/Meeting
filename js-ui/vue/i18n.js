import Vue from 'vue'
import GetTextPlugin from 'vue-gettext'
import { translate } from 'vue-gettext'


const catalog = window.translations || (window.django && window.django.catalog) || null
const langCode = (window.MIVIDAS && window.MIVIDAS.language) || 'en'


Vue.use(GetTextPlugin, {
    availableLanguages: {
        en: 'English',
        sv: 'Swedish',
    },
    defaultLanguage: langCode,
    languageVmMixin: {
        computed: {
            currentKebabCase: function () {
                return this.current.toLowerCase().replace('_', '-')
            },
        },
    },
    translations: { [langCode]: catalog || {} },
    silent: true,
})

window.MIVIDAS = window.MIVIDAS || {}

if (catalog) {
    window.MIVIDAS.$gettext = translate.gettext
}
window.MIVIDAS.$gettextInterpolate = Vue.prototype.$gettextInterpolate

