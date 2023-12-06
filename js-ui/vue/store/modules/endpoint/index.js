import Vue from 'vue'
import { getKey, freshTimestamp } from './helpers'
import { baseURL } from '@/consts'
import { idMap } from '@/vue/helpers/store'
import { endpointStatusNames } from '@/vue/store/modules/endpoint/consts'
import {singleGet} from '@/vue/helpers/store'
import { replaceQuery } from '@/vue/helpers/url'

export default {
    state() {
        return {
            endpoints: {},
            incoming: {},
            status: {},
            configuration: {},
            commands: {},
            commandQueue: [],
            backups: {},
            firmwares: {},
            bookings: {},
            templates: {},
            report: {},
            tasks: {},

            settings: {},

            proxies: {},
            proxyStatusChanges: [],
            latestProxyStatusChanges: [],

            activeConfiguration: {},
        }
    },
    actions: {
        singleGet,
        async getSettings({ dispatch, commit }) {
            const settings = await dispatch('singleGet', 'endpointsettings/')
            commit('setCustomerSettings', settings)
            return settings
        },
        async setSettings(context, form) {
            return this.api().patch(`endpointsettings/${form.id}/`, form)
        },
        async getDomains() {
            return this.api().get('endpointsettings/domains/')
        },
        async getDefaultPasswords() {
            return this.api().get('endpointsettings/passwords/')
        },
        async setDefaultPasswords(context, passwords) {
            return this.api().post('endpointsettings/set_passwords/', { passwords })
        },
        async getAutoRegisterIpNets() {
            return this.api().get('endpointsettings/ip_nets/')
        },
        async setAutoRegisterIpNets(context, ip_nets) {
            return this.api().post('endpointsettings/set_ip_nets/', { ip_nets })
        },
        async getEndpoints({ dispatch, commit }) {
            const endpoints = await dispatch('singleGet', 'endpoint/')
            commit('setEndpoints', endpoints)
        },
        async getIncoming({ dispatch, commit }) {
            const incoming = await dispatch('singleGet', 'endpoint/incoming/')
            commit('setIncoming', incoming)
        },
        async getEndpoint({ dispatch, commit }, id) {
            const endpoint = await dispatch('singleGet', `endpoint/${id}/`)
            commit('updateEndpoint', endpoint)
            return endpoint
        },
        async getHeadCount(context, { id, hours = 48 }) {
            return this.api().get(`endpoint/${id}/head_count/?hours=${hours}`)
        },
        async requireEndpoint({ dispatch, state }, id) {
            if (state.endpoints[id] && state.endpoints[id]._fullyLoaded > freshTimestamp('endpoint')) {
                return state.endpoints[id]
            }
            return dispatch('getEndpoint', id)
        },
        async deleteEndpoint({ commit }, id) {
            const endpoint = await this.api(true).delete(`endpoint/${id}/`)
            commit('deleteEndpoint', id)
            return endpoint
        },
        async createEndpoint({ commit }, data) {
            const endpoint = await this.api().post('endpoint/', data)
            commit('updateEndpoint', endpoint)
            return endpoint
        },
        async updateEndpoint({ commit }, { id, data }) {
            const endpoint = await this.api().patch(`endpoint/${id}/`, data)
            commit('updateEndpoint', endpoint)
            return endpoint
        },
        async createEndpointBulk({ commit }, endpointBulkData) {
            const response = await this.api().post('endpoint/bulk_create/', endpointBulkData)

            response.map(endpoint => commit('updateEndpoint', endpoint))
            return response
        },
        async updateBulk({ commit }, endpointBulkData) {
            const response = await this.api().patch('endpoint/bulk_update/', endpointBulkData)
            const endpoints = response.endpoints || []
            endpoints.forEach(endpoint => endpoint.id && commit('updateEndpoint', endpoint))
            return response
        },
        async deleteBulk({ dispatch }, endpoints) {
            const result = await this.api().post('endpoint/bulk_delete/', {endpoints})
            dispatch('getEndpoints')
            return result
        },
        async getStatus({ commit, dispatch }, endpointId) {
            try {
                const endpointStatus = await dispatch('singleGet', `endpoint/${endpointId}/status/`)
                commit('setEndpointStatus', { endpointId, status: endpointStatus })
                return endpointStatus
            } catch (e) {
                if (e.new_status === undefined) throw e
                const newStatus = { status: e.new_status }
                commit('setEndpointStatus', { endpointId, status: newStatus, upgrade: {} })
                return newStatus
            }
        },
        async getFullStatus({ commit }, endpointId) {
            const endpointStatus = await this.api().get(`endpoint/${endpointId}/status_data/`)
            commit('setStatus', { id: endpointId, status: endpointStatus })
            return endpointStatus.data
        },
        async getActiveMeeting(context, endpointId) {
            return this.api().get(`endpoint/${endpointId}/active_meeting_details/`)
        },
        async getCallHistory(context, endpointId) {
            return this.api().get(`endpoint/${endpointId}/call_history/`)
        },
        async getCallHistoryInfo(context, { endpointId, historyId }) {
            return this.api().get(`endpoint/${endpointId}/call_debug/${historyId}/`)
        },
        async getCalls(context, endpointId) {
            return this.api().get(`endpoint/${endpointId}/calls/`)
        },
        async getTasks({ commit }, params) {
            const { provisionId, endpointId, search, status, action, changedSince, orderBy } = params || {}
            const tasks = await this.api().get(replaceQuery('endpointtask/', {
                provision: provisionId,
                endpoint: endpointId,
                search,
                status,
                action,
                changed_since: changedSince,
                order_by: orderBy,
            }))
            if (changedSince) {
                commit('updateTasks', tasks)
            } else {
                commit('setTasks', tasks)
            }
            return tasks
        },
        async getEndpointTasks({ commit }, endpointId) {
            const tasks = await this.api().get(`endpointtask/?endpoint=${endpointId}`)
            commit('setTasks', tasks)
            return tasks
        },
        async getTask({ commit }, id) {
            const task = await this.api().get(`endpointtask/${id}/`)
            commit('updateTask', task)
            return task
        },
        async cancelTask({ commit }, id) {
            const task = await this.api().post(`endpointtask/${id}/cancel/`)
            commit('updateTask', task)
            return task
        },
        async retryTask({ commit }, id) {
            const task = await this.api().post(`endpointtask/${id}/retry/`)
            commit('updateTask', task)
            return task
        },
        async getProxies({ commit }) {
            const endpointProxies = await this.api().get('endpointproxy/')
            commit('setProxies', endpointProxies)
            return endpointProxies
        },
        async updateProxy({ dispatch }, data) {
            const response = await this.api().patch(`endpointproxy/${data.id}/`, data)
            dispatch('getProxies')
            return response
        },
        async deleteProxy({ dispatch }, id) {
            const response = await this.api().delete(`endpointproxy/${id}/`)
            dispatch('getProxies')
            return response
        },
        async getProxyStatusChanges({ commit }) {
            const changes = await this.api().get('endpointproxy/status/latest/')
            commit('setProxyStatusChanges', changes)
            return changes
        },
        async getLatestProxyStatusChanges({ commit }) {
            const changes = await this.api().get('endpointproxy/status/per_proxy/')
            commit('setLatestProxyStatusChanges', changes)
            return changes
        },
        async getDialInfo(context, endpointId) {
            return this.api().get(`endpoint/${endpointId}/dial_info/`)
        },
        async getProvisionStatus(context, endpointId) {
            return this.api().get(`endpoint/${endpointId}/provision_status/`)
        },
        async callControl(context, { endpointId, action, argument }) {
            return this.api().post(`endpoint/${endpointId}/call_control/`, {
                action,
                argument,
            })
        },
        async getFilters() {
            return this.api().get('endpoint/filters/')
        },
        async getBackups({ commit }, endpointId) {
            const endpointBackups = await this.api().get(`endpointbackup/?endpoint=${endpointId}`)
            commit('setBackups', endpointBackups)
        },
        async getFirmwares({ commit }) {
            const endpointFirmwares = await this.api().get('endpointfirmware/')
            commit('setFirmwares', endpointFirmwares)
        },
        async deleteFirmware(context, firmwareId) {
            return this.api().delete(`endpointfirmware/${firmwareId}/`)
        },
        async copyFirmware(context, { firmwareId, ...form }) {
            return this.api().post(`endpointfirmware/${firmwareId}/copy/`, form)
        },
        async installFirmware(context, { endpointId, firmwareId, force, constraint }) {
            return this.api().post(`endpoint/${endpointId}/install_firmware/`, {
                firmware: firmwareId,
                force,
                constraint,
            })
        },
        async downloadFirmware(context, firmwareId) {
            const url = `${baseURL}endpointfirmware/${firmwareId}/download/`
            window.open ? window.open(url) : location.href = url
        },
        async backupEndpoint({ commit }, endpointId) {
            const response = await this.api().post(`endpoint/${endpointId}/backup/`)
            commit('updateBackup', response)
            return response
        },
        async deleteBackup({ commit }, backupId) {
            const response =  await this.api().delete(`endpointbackup/${backupId}/`)
            commit('deleteBackup', backupId)
            return response
        },
        async restoreBackup(context, backupId) {
            return this.api().post(`endpointbackup/${backupId}/restore/`)
        },
        async downloadBackup(context, backupId) {
            const url = `${baseURL}endpointbackup/${backupId}/download/`
            window.open(url)
        },
        async getConfiguration({ commit, dispatch }, endpointId) {
            const endpointConfiguration = await dispatch(
                'singleGet',
                `endpoint/${endpointId}/configuration_data/`
            )
            commit('setConfiguration', { id: endpointId, configuration: endpointConfiguration })
            return endpointConfiguration.data
        },
        async getCommands({ commit }, endpointId) {
            const endpointCommands = await this.api().get(`endpoint/${endpointId}/commands_data/`)
            commit('setCommands', { id: endpointId, commands: endpointCommands })
            return endpointCommands.data
        },
        async runCommand(context, { endpointId, command, args, body }) {
            return await this.api().post(`endpoint/${endpointId}/run_command/`, {
                command,
                arguments: args,
                body: body || '',
            })
        },
        async queueCommand({ commit }, { command, args, body }) {
            commit('queueCommand', { command, args: {...args}, body })
        },
        async setConfiguration(context, { endpointId, settings }) {
            return await this.api().post(`endpoint/${endpointId}/set_configuration/`, {
                settings,
            })
        },
        async saveTemplate(context, data) {
            return await this.api().post('endpointtemplate/', data)
        },
        async deleteTemplate({ commit }, templateId) {
            const response = await this.api().delete(`endpointtemplate/${templateId}/`)
            commit('deleteTemplate', templateId)
            return response
        },
        async getTemplates({ commit }) {
            const response = await this.api().get('endpointtemplate/')
            commit('setTemplates', response)
        },
        async createReport(context, { endpoints, values }) {
            return this.api().post('endpoint/report/', { endpoints, values })
        },
        async uploadFirmware({ dispatch }, { form, progress }) {
            const instance = this.api()
            if (progress)
                instance.defaults.onUploadProgress = e => progress(Math.floor(e.loaded * 1.0) / e.total)

            const response = await instance.post('endpointfirmware/', form)
            dispatch('getFirmwares', response)
            return response
        },
        async uploadCommand(context, { endpointId, form, progress }) {
            const instance = this.api()
            if (progress)
                instance.defaults.onUploadProgress = e => progress(Math.floor(e.loaded * 1.0) / e.total)

            return await instance.post(`endpoint/${endpointId}/commands_data/`, form)
        },
        async getAllBookings({ commit }) {
            const response = await this.api().get('endpoint/all_bookings/')
            commit('setBookings', response)
            return response
        },
        async getBookings({ commit }, endpointId) {
            const response = await this.api().get(`endpoint/${endpointId}/bookings/`)
            commit('updateBookings', response)
            return response
        },
        async setSIPAliases({ commit }, { endpointId, aliases }) {
            const response = await this.api().post(`endpoint/${endpointId}/set_sip_aliases/`, {
                sip: aliases,
            })
            commit('updateEndpoint', response)
            return response
        },
        async provision(context, data) {
            return this.api().post('endpoint/provision/', data)
        },
        async excelExport(context, endpointIds) {
            return this.api().post('endpoint/export/', { endpoints: endpointIds })
        },
        excelExportDownload(context, endpointIds) {
            const url = `${baseURL}endpoint/export/?endpoints=${endpointIds.join(',')}`
            return window.open ? window.open(url) : location.href = url
        }
    },
    getters: {
        endpoints(state) {
            return Object.values(state.endpoints).map(e => ({
                ...e,
                status_text: endpointStatusNames[e.status_code],
                uri: e.sip || e.h323 || e.h323_e164,
                type: {
                    0: 'Other',
                    10: 'Cisco CE',
                    20: 'Cisco CMS',
                }[e.manufacturer],
            }))
        },
        bookings(state) {
            return Object.values(state.bookings)
        },
    },
    mutations: {
        updateEndpoint(state, endpoint) {
            const cur = state.endpoints[endpoint.id] || { status: {} }
            Vue.set(state.endpoints, endpoint.id, {
                ...cur,
                ...endpoint,
                uri: endpoint.uri || endpoint.sip || endpoint.h323 || endpoint.h323_e164 || cur.uri,
                status: { ...cur.status, ...endpoint.status },
                _fullyLoaded: new Date().getTime(),
            })
        },

        setEndpointStatus(state, { endpointId, status }) {
            const cur = state.endpoints[endpointId]
            if (!cur) return
            cur.status_code = status.status
            cur.online = cur.status_code > 0
            cur.status = {
                ...cur.status,
                ...status,
            }
        },
        setIncoming(state, endpoints) {
            state.incoming = idMap(endpoints)
        },
        setEndpoints(state, endpoints) {
            const preferFullyLoaded = endpoint => {
                const cur = state.endpoints[endpoint.id]
                const uri = endpoint.uri || endpoint.sip || endpoint.h323 || endpoint.h323_e164 || cur?.uri || ''

                const result = {
                    ...endpoint,
                    uri,
                    online: endpoint.status_code > 0,
                    status: endpoint.status || {},
                }
                if (cur && cur._fullyLoaded) { // merge with previously loaded
                    return {
                        ...cur,
                        ...result,
                        status: {
                            ...cur.status,
                            ...result.status,
                        },
                    }
                }
                return result
            }

            const result = {}
            endpoints.forEach(e => (result[e.id] = preferFullyLoaded(e)))
            state.endpoints = result
        },
        deleteEndpoint(state, id) {
            delete state.endpoints[id]
        },
        setTasks(state, tasks) {
            state.tasks = idMap(tasks)
        },
        updateTask(state, task) {
            state.tasks = { ...state.tasks, [task.id]: task }
        },
        setProxies(state, proxies) {
            const result = {}
            proxies.forEach(p => (result[p.id] = p))
            state.proxies = result
        },
        setProxyStatusChanges(state, changes) {
            Vue.set(state, 'proxyStatusChanges', changes)
        },
        setLatestProxyStatusChanges(state, changes) {
            Vue.set(state, 'latestProxyStatusChanges', changes)
        },
        setStatus(state, { id, status }) {
            state.status = { ...state.status, [id]: status }
        },
        setConfiguration(state, { id, configuration }) {
            state.configuration = { ...state.configuration, [id]: configuration }
        },
        setCommands(state, { id, commands }) {
            state.commands = { ...state.commands, [id]: commands }
        },
        queueCommand(state, { command, args, body }) {
            state.commandQueue.push({ command, arguments: args, body})
        },
        queueUpdateCommand(state, { index, command }) {
            state.commandQueue.splice(index, 1, { ...command })
        },
        queueInsertCommand(state, { index, command }) {
            state.commandQueue.splice(index, 0, { ...command })
        },
        queueRemoveCommand(state, index) {
            Vue.delete(state.commandQueue, index)
        },
        clearCommandQueue(state) {
            state.commandQueue = []
        },
        setCommandQueue(state, commands) {
            state.commandQueue = commands || []
        },
        setBackups(state, backups) {
            state.backups = { ...state.backups, ...idMap(backups) }
        },
        updateBackup(state, backup) {
            state.backups = { ...state.backups, [backup.id]: backup }
        },
        deleteBackup(state, backupId) {
            Vue.delete(state.backups, backupId)
        },
        setBookings(state, bookings) {
            state.bookings = idMap(bookings.map(b => ({ ...b, endpoints: idMap(b.endpoint || []) })))
        },
        updateBookings(state, bookings) {
            state.bookings = {
                ...state.bookings,
                ...idMap(bookings.map(b => ({ ...b, endpoints: idMap(b.endpoints || []) }))),
            }
        },
        setFirmwares(state, firmwares) {
            state.firmwares = idMap(firmwares)
        },
        updateFirmware(state, firmware) {
            state.firmwares = { ...state.firmwares, [firmware.id]: firmware }
        },
        setTemplates(state, templates) {
            const result = {}
            templates.forEach(t => {
                const settings = typeof t.settings == 'string' ? JSON.parse(t.settings) : t.settings
                result[t.id] = {
                    ...t,
                    settings: settings.map(s => ({ ...s, path: s.path || s.key })),
                }
            })
            state.templates = result
        },
        deleteTemplate(state, templateId) {
            Vue.delete(state.templates, templateId)
        },
        clearActiveConfiguration(state) {
            state.activeConfiguration = {}
        },
        removeActiveConfiguration(state, setting) {
            Vue.delete(state.activeConfiguration, getKey(setting))
        },
        setActiveConfiguration(state, settings) {
            const result = []
            settings.forEach(s => {
                const key = getKey(s)
                result[key] = { ...s, key: key }
            })
            state.activeConfiguration = result
        },
        updateConfiguration(state, { setting, value }) {
            const key = getKey(setting)
            if (value === null) {
                Vue.delete(state.activeConfiguration, key)
            } else {
                state.activeConfiguration = {
                    ...state.activeConfiguration,
                    [key]: { path: setting.path, setting, value, key },
                }
            }
        },
        updateReport(state, { status, active }) {
            const key = getKey(status)
            if (!active) {
                Vue.delete(state.report, key)
            } else {
                Vue.set(state.report, key, status.path)
            }
        },
        setCustomerSettings(state, settings) {
            state.settings = settings
        },
    },
    namespaced: true,
}
