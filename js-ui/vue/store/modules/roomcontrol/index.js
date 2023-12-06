import Vue from 'vue'
import { idMap } from '@/vue/helpers/store'
import { timestamp } from '@/vue/helpers/datetime'

function loadControl(control) {

    const panels = []
    const macros = []

    control.files.forEach(f => {
        const ext = f.name.split('.').pop()
        if (ext.toLowerCase() === 'xml') {
            panels.push(f)
        }
        if (ext.toLowerCase() === 'js') {
            macros.push(f)
        }
    })

    return {
        ...control,
        panels,
        macros,
        isPanel: panels.length,
        isMacro: macros.length,
        urlExport: control.url_export,
        created: timestamp(control.ts_created)
    }
}

export default {
    state() {
        return {
            controls: {},
            templates: {},
        }
    },
    actions: {

        // Control

        async getControls({ commit }) {
            const controls = await this.api().get('roomcontrols/')
            commit('setControls', controls)
            return controls
        },
        async createControl({ commit }, { form, progress }) {
            const instance = this.api()
            if (progress)
                instance.defaults.onUploadProgress = e => progress(Math.floor(e.loaded * 1.0) / e.total)

            const response = await instance.post('roomcontrols/', form)
            commit('updateControl', response)
            return response
        },
        async deleteControl({ commit }, id) {
            const response = await this.api().delete(`roomcontrols/${id}/`)
            commit('deleteControl', id)
            return response
        },
        async updateControl({ commit }, { id, data }) {
            const response = await this.api().patch(`roomcontrols/${id}/`, data)
            commit('updateControl', response)
            return response
        },
        async addControlFiles({ commit }, { id, data, progress }) {
            const instance = this.api()
            if (progress)
                instance.defaults.onUploadProgress = e => progress(Math.floor(e.loaded * 1.0) / e.total)

            const response = await instance.post(`roomcontrols/${id}/add_files/`, data)
            commit('updateControl', response)
            return response
        },
        async deleteControlFile({ commit }, id) {
            const response = await this.api().delete(`roomcontrol_files/${id}/`)
            commit('updateControl', response)
            return response
        },

        // Template

        async getTemplates({ commit }) {
            const templates = await this.api().get('roomcontrol_templates/')
            commit('setTemplates', templates)

            return templates
        },
        async createTemplate({ dispatch }, data) {
            const response = await this.api().post('roomcontrol_templates/', data)
            dispatch('updateTemplate', response)
            return response
        },
        async deleteTemplate({ commit }, id) {
            const response = await this.api().delete(`roomcontrol_templates/${id}/`)
            commit('deleteTemplate', id)
            return response
        },
        async updateTemplate({ commit }, { id, data }) {
            const response = await this.api().patch(`roomcontrol_templates/${id}/`, data)
            commit('updateTemplate', response)
            return response
        },

        async getExportUrl(options, controls) {
            return await this.api().post('roomcontrols/get_export_url/', {
                controls
            })
        }
    },
    mutations: {
        setControls(state, controls) {
            state.controls = idMap(controls.map(loadControl))
        },
        deleteControl(state, id) {
            Vue.delete(state.controls, id)
            Object.values(state.templates).forEach(template => {
                const index = template.controls.indexOf(id)
                if (index != -1) template.controls.splice(index, 1)
            })
        },
        updateControl(state, control) {
            state.controls = { ...state.controls, [control.id]: loadControl(control) }
        },
        setTemplates(state, templates) {
            state.templates = idMap(templates)
        },
        deleteTemplate(state, id) {
            Vue.delete(state.templates, id)
        },
        updateTemplate(state, template) {
            state.templates = { ...state.templates, [template.id]: template }
        },
    },
    namespaced: true,
}
