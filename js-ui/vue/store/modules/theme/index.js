import Vue from 'vue'

export default {
    state() {
        return {
            theme: {
                logo: null,
                darkMode: true
            },
        }
    },
    actions: {
        async getTheme({ commit }) {
            const response = await this.api().get('themesettings/1/')
            commit('setTheme', response)
            return response
        },
        async updateTheme({ commit }, { form, progress }) {
            const instance = this.api()
            if (progress)
                instance.defaults.onUploadProgress = e => progress(Math.floor(e.loaded * 1.0) / e.total)

            const response = await instance.patch('themesettings/1/', form)
            commit('setTheme', response)
            return response
        },
    },
    mutations: {
        setTheme(state, theme) {
            Vue.set(state, 'theme', {
                logo: theme.logo_image,
                favicon: theme.favicon,
                darkMode: theme.dark_mode
            })
        },
    },
    namespaced: true,
}
