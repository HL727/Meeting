import {endpointModelFamilies} from '@/vue/store/modules/endpoint/consts'

function getValue(setting, rootState) {
    const key = getKey(setting)
    const cur = rootState.endpoint.activeConfiguration[key]

    return cur ? cur.value : undefined
}

function getKey(setting) {
    return setting.path.join('>')
}

function flattenConfigurationTree(tree) {
    const result = []
    const recurse = item => {
        const setting = item[3]
        if (setting && setting.is_setting) {
            result.push(setting)
        }
        const children = item[2] || []
        children.map(recurse)
    }

    tree.map(recurse)
    return result
}

function filterInternalSettings(configuration) {
    const paths = ['Network/IPv4', 'Network/IPv6', 'SystemUnit/(Name|ContactName)', 'SIP/.*(DisplayName|URI)', '/ContactInfo/Name$', 'H323/.*(ID|E164)$']
        .map(p => new RegExp(p))

    return configuration.filter(c => {
        const fullPath = c.path.join('/').replace(/\[\d+\]/g, '')
        return !paths.some(p => fullPath.match(p))
    })
}

function populateSettingsData(bareSettings, configurationTree) {
    const allSettings = {}
    flattenConfigurationTree(configurationTree).forEach(c => (allSettings[c.path.join('/')] = c))

    return bareSettings.map(s => ({ ...s, setting: s.setting || allSettings[s.path.join('/')] }))
}

function freshTimestamp(type) {
    let timeout = 5
    if (type === 'endpoint') timeout = 5
    return new Date().getTime() - timeout * 60 * 60
}

export function extractFilenameProducts(filename) {
    const m = filename.match(/(s5\d+)(tc|ce)[\d_]/)
    if (!m) return ''
    return endpointModelFamilies[m[1]] || ''
}

export function matchFirmwareModels(models, haystack) {
    const result = []

    models.forEach(model => {
        const normalizedModel = model.replace(' Series', '')
        haystack.map(product => {
            if (product.indexOf(normalizedModel) !== -1) result.push(product)
        })
    })
    return result
}

export function matchFilenameFirmwareModels(filename, haystack) {
    const models = extractFilenameProducts(filename || '')
    if (!models) return []
    return matchFirmwareModels(models.split(', '), haystack)
}

export {
    getKey,
    getValue,
    flattenConfigurationTree,
    filterInternalSettings,
    populateSettingsData,
    freshTimestamp,
}
