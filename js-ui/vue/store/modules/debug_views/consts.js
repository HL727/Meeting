
import { $gettext, $ngettext } from '@/vue/helpers/translate'

function debugViewStructure(settings) {
    const result = {}
    Object.values(debugViewStructurePerProduct(settings)).forEach(debugViews => Object.assign(result, debugViews))
    return result
}

function debugViewStructurePerProduct(settings) {

    const result = {}

    if (settings.enableCore) {
        result.core = coreDebugViewStructure(settings)
    }
    if (settings.enableEPM) {
        result.epm = epmDebugViewStructure()
    }
    result.shared = sharedLogStructure()

    const setObjectKeys = (structs) => {
        Object.keys(structs).forEach(key => {
            structs[key].key = key
        })
        return structs
    }

    Object.values(result).forEach(setObjectKeys)
    return result
}

// eslint-disable-next-line max-lines-per-function
function sharedLogStructure() {

    return {
        audit_log: {
            title: $gettext('Audit'),
            description: $gettext('Audit logs'),
            contentType: 'text',
            headers: [
                { text: 'IP', value: 'ip' },
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: $gettext('Område'), value: 'scope' },
                { text: $gettext('Åtgärd'), value: 'action' },
                { text: $gettext('Typ'), value: 'type' },
                { text: $gettext('Användarnamn'), value: 'username' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {
                username: { text: $gettext('Användarnamn'), type: 'text' },
                scope: { text: $gettext('Område'), type: 'text' },
                ip: { text: 'IP', type: 'text' },
                cluster: { text: $gettext('Kluster'), type: 'number' },
                customer: { text: $gettext('Kund'), type: 'number' },
                path: { text: $gettext('URL Path'), type: 'text' },
            }

        },
        error_log: {
            title: $gettext('Fellogg'),
            description: $gettext('Loggade fel i systemet'),
            contentType: 'text',
            headers: [
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: $gettext('Typ'), value: 'type' },
                { text: $gettext('Rubrik'), value: 'text' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {
                type: { text: $gettext('Typ'), type: 'text' },
            }

        },
        trace_log: {
            title: $gettext('API trace-logg'),
            description: $gettext('Loggade anrop för utökad loggning'),
            contentType: 'object',
            headers: [
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: $gettext('Metod'), value: 'method' },
                { text: $gettext('URL'), value: 'url_base' },
                { text: $ngettext('Kluster', 'Kluster', 1), value: 'cluster_id' },
                { text: $ngettext('System', 'System', 1), value: 'endpoint_id' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {
                method: { text: $gettext('Metod'), type: 'text' },
                cluster_id: { text: $gettext('Kluster'), type: 'number' },
                provider_id: { text: $gettext('MCU'), type: 'number' },
                customer_id: { text: $gettext('Kund'), type: 'number' },
                endpoint_id: { text: $gettext('Endpoint ID'), type: 'text' },
            }

        },
    }
}

// eslint-disable-next-line max-lines-per-function
function coreDebugViewStructure(settings) {
    return {
        acanocdr: {
            title: $gettext('CMS CDR'),
            description: $gettext('CDR-log från Cisco Meeting Server'),
            contentType: 'text',
            headers: [
                { text: 'IP', value: 'ip' },
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: $gettext('Antal'), value: 'count' },
                { text: $gettext('Typ'), value: 'types' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {
                ip: { text: 'IP', type: 'text' },
            },
        },
        acanocdrspam: {
            title: $gettext('CMS CDR spambox'),
            description: $gettext('Legs som är nästan 100% bara SIP bot-spam som annars skulle belasta systemet'),
            contentType: 'text',
            headers: [
                { text: 'IP', value: 'ip' },
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {
                ip: { text: 'IP', type: 'text' },
            },
        },
        pexip_event: {
            title: $gettext('Pexip Event Sink'),
            description: $gettext('Pexip Event Sink data'),
            contentType: 'object',
            headers: [
                { text: $ngettext('Kluster', 'Kluster', 1), value: 'cluster_id' },
                { text: $gettext('IP'), value: 'ip' },
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: $gettext('Typ'), value: 'type' },
                { text: $gettext('Uuid start'), value: 'uuid_start' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {
                ip: { text: 'IP', type: 'text' },
                type: { text: $gettext('Typ'), type: 'text' },
                uuid_start__startswith: { text: $gettext('Början på call_id/uuid/name'), type: 'text' },
            },
        },
        pexip_history: {
            title: $gettext('Pexip History API'),
            description: $gettext('Call statistics fetched from API'),
            contentType: 'text',
            headers: [
                { text: $gettext('Cluster'), value: 'cluster_id' },
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: $gettext('Typ'), value: 'type' },
                { text: $gettext('Antal'), value: 'count' },
                { text: $gettext('Första'), value: 'first_start' },
                { text: $gettext('Sista'), value: 'last_start' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {
                ip: { text: 'IP', type: 'text' },
                first_start__gte: { text: $gettext('Första fr.o.m.'), type: 'datetime' },
                first_start__lte: { text: $gettext('Första t.o.m.'), type: 'datetime' },
                last_start__gte: { text: $gettext('Sista fr.o.m.'), type: 'datetime' },
                last_start__lte: { text: $gettext('Sista t.o.m.'), type: 'datetime' },
            },
        },
        pexip_policy: {
            title: $gettext('Pexip Policy'),
            description: $gettext('Pexip external policy requests and responses'),
            contentType: 'object',
            headers: [
                { text: $ngettext('Kluster', 'Kluster', 1), value: 'cluster_id' },
                { text: $gettext('IP'), value: 'ip' },
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: $gettext('Action'), value: 'action' },
                { text: $gettext('Service type'), value: 'service_type' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {
                ip: { text: 'IP', type: 'text' },
                type: { text: $gettext('Typ'), type: 'text' },
                service_type: { text: $gettext('Service typ'), type: 'text' },
                action: { text: $gettext('Action'), type: 'text' },
            },
        },
        ...(settings.perms.policy ? { policy: {
            to: {name: 'policy_log'},
            title: $gettext('Policy Debug'),
            description: $gettext('Aktiva kunder och policybeslut'),
        } } : {}
        ),
        vcs: {
            title: $gettext('VCS'),
            description: $gettext('VCS statistik'),
            contentType: 'text-list',
            headers: [
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: $gettext('Start'), value: 'ts_start' },
                { text: $gettext('Stop'), value: 'ts_stop' },
                { text: $gettext('Delar'), value: 'partsCount' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {},
        },
    }

}

// eslint-disable-next-line max-lines-per-function
function epmDebugViewStructure() {
    return {
        email: {
            title: $gettext('E-post'),
            description: $gettext('Innehåll från vidarebefordrade e-postmeddelanden'),
            contentType: 'parts',
            headers: [
                { text: $gettext('Från'), value: 'sender' },
                { text: $gettext('Ämne'), value: 'subject' },
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: $gettext('Delar'), value: 'partsCount' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {
                sender: { text: $gettext('Från'), type: 'text' },
            },
        },
        cisco: {
            title: $gettext('Cisco Endpoint'),
            description: $gettext('Cisco Endpoint HTTP Events'),
            contentType: 'text',
            headers: [
                { text: 'IP', value: 'ip' },
                { text: $ngettext('System', 'System', 1), value: 'endpoint' },
                { text: $gettext('Event'), value: 'event' },
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {
                ip: { text: 'IP', type: 'text' },
                endpoint: { text: $gettext('Endpoint ID'), type: 'text' },
                event: { text: $gettext('Event'), type: 'text' },
            },
        },
        cisco_provision: {
            title: $gettext('Cisco Endpoint provision'),
            description: $gettext('Passiv provision meddelanden'),
            contentType: 'text',
            headers: [
                { text: 'IP', value: 'ip' },
                { text: $ngettext('System', 'System', 1), value: 'endpoint' },
                { text: $gettext('Event'), value: 'event' },
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {
                ip: { text: 'IP', type: 'text' },
                endpoint: { text: $gettext('Endpoint ID'), type: 'text' },
                event: { text: $gettext('Event'), type: 'text' },
            },
        },
        poly_provision: {
            title: $gettext('Poly Endpoint provision'),
            description: $gettext('Passiv provision meddelanden'),
            contentType: 'text',
            headers: [
                { text: 'IP', value: 'ip' },
                { text: $gettext('Endpoint'), value: 'endpoint' },
                { text: $gettext('Event'), value: 'event' },
                { text: $gettext('Skapad'), value: 'ts_created' },
                { text: '', value: 'button', align: 'end' },
            ],
            filters: {
                ip: { text: 'IP', type: 'text' },
                endpoint: { text: $gettext('Endpoint ID'), type: 'text' },
                event: { text: $gettext('Event'), type: 'text' },
            },
        },
    }
}

export { debugViewStructure, debugViewStructurePerProduct }
