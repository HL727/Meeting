import json

from django.views.generic import TemplateView
import re
from django.utils.translation import gettext_lazy as _

from provider.exceptions import ResponseError
from provider.models.provider import Provider

from django.http import HttpResponse

from defusedxml.cElementTree import fromstring as safe_xml_fromstring

import urllib.request, urllib.parse, urllib.error

from customer.view_mixins import LoginRequiredMixin, CustomerMixin
from shared.utils import prettify_xml

URLS = [
    'accessQuery',
    'callBrandingProfiles',
    'callBridgeGroups',
    'callBridges',
    'calls',
    'callProfiles',
    'callLegs',
    'callLegProfiles',
    'clusterLicensing',
    'clusterLicensing/raw',
    'dialInSecurityProfiles',
    'compatibilityProfiles',
    'conversationIdQuery',
    'cospaceBulkParameterSets',
    'cospaceBulkSyncs',
    'coSpaces',
    'dialTransforms',
    'directorySearchLocations',
    'dtmfProfiles',
    'forwardingDialPlanRules',
    'inboundDialPlanRules',
    'ivrs',
    'ivrBrandingProfiles',
    'layoutTemplates',
    'ldapMappings',
    'ldapServers',
    'ldapSources',
    'ldapSyncs',
    'outboundDialPlanRules',
    'participants',
    'recorders',
    'streamers',
    'system/alarms',
    'system/cdrReceiver',
    'system/cdrReceivers',
    'system/configuration/cluster',
    'system/configuration/xmpp',
    'system/database',
    'system/diagnostics',
    'system/licensing',
    'system/load',
    'system/MPLicenseUsage',
    'system/MPLicenseUsage/knownHosts',
    'system/multipartyLicensing',
    'system/multipartyLicensing/activePersonalLicenses',
    'system/profiles',
    'system/profiles/effectiveWebBridgeProfile',
    'system/status',
    'tenantGroups',
    'tenants',
    'turnServers',
    'uriUsageQuery',
    'userProfiles',
    'users',
    'webBridges',
    'webBridgeProfiles',

]

PEXIP_URLS = [
    'status/v1/alarm',
    'status/v1/backplane',
    'status/v1/cloud_monitored_location',
    'status/v1/cloud_node',
    'status/v1/cloud_overflow_location',
    'status/v1/conference',
    'status/v1/conference_shard',
    'status/v1/conference_sync',
    'status/v1/exchange_scheduler',
    'status/v1/licensing',
    'status/v1/mjx_meeting',
    'status/v1/participant',
    'status/v1/registration_alias',
    'status/v1/scheduling_operation',
    'status/v1/system_location',
    'status/v1/worker_vm',

    'history/v1/alarm',
    'history/v1/backplane',
    'history/v1/backplane_media_stream',
    'history/v1/conference',
    'history/v1/media_stream',
    'history/v1/participant',
    'history/v1/workervm_status_event',

    'configuration/v1/adfs_auth_server',
    'configuration/v1/adfs_auth_server_domain',
    'configuration/v1/authentication',
    'configuration/v1/autobackup',
    'configuration/v1/automatic_participant',
    'configuration/v1/azure_tenant',
    'configuration/v1/ca_certificate',
    'configuration/v1/certificate_signing_request',
    'configuration/v1/conference',
    'configuration/v1/conference_alias',
    'configuration/v1/conference_sync_template',
    'configuration/v1/device',
    'configuration/v1/diagnostic_graphs',
    'configuration/v1/dns_server',
    'configuration/v1/end_user',
    'configuration/v1/event_sink',
    'configuration/v1/exchange_domain',
    'configuration/v1/gateway_routing_rule',
    'configuration/v1/global',
    'configuration/v1/gms_access_token',
    'configuration/v1/google_auth_server',
    'configuration/v1/google_auth_server_domain',
    'configuration/v1/h323_gatekeeper',
    'configuration/v1/host_system',
    'configuration/v1/http_proxy',
    'configuration/v1/ivr_theme',
    'configuration/v1/ldap_role',
    'configuration/v1/ldap_sync_field',
    'configuration/v1/ldap_sync_source',
    'configuration/v1/licence',
    'configuration/v1/licence_request',
    'configuration/v1/log_level',
    'configuration/v1/management_vm',
    'configuration/v1/mjx_endpoint',
    'configuration/v1/mjx_endpoint_group',
    'configuration/v1/mjx_exchange_autodiscover_url',
    'configuration/v1/mjx_exchange_deployment',
    'configuration/v1/mjx_google_deployment',
    'configuration/v1/mjx_integration',
    'configuration/v1/mjx_meeting_processing_rule',
    'configuration/v1/ms_exchange_connector',
    'configuration/v1/mssip_proxy',
    'configuration/v1/ntp_server',
    'configuration/v1/permission',
    'configuration/v1/policy_server',
    'configuration/v1/pss',
    'configuration/v1/recurring_conference',
    'configuration/v1/registration',
    'configuration/v1/role',
    'configuration/v1/scheduled_alias',
    'configuration/v1/scheduled_conference',
    'configuration/v1/sip_credential',
    'configuration/v1/sip_proxy',
    'configuration/v1/smtp_server',
    'configuration/v1/snmp_network_management_system',
    'configuration/v1/static_route',
    'configuration/v1/stun_server',
    'configuration/v1/syslog_server',
    'configuration/v1/system_backup',
    'configuration/v1/system_location',
    'configuration/v1/teams_proxy',
    'configuration/v1/tls_certificate',
    'configuration/v1/turn_server',
    'command/v1/participant/dial',
    'command/v1/participant/disconnect',
    'command/v1/participant/mute',
    'command/v1/participant/role',
    'command/v1/participant/transfer',
    'command/v1/participant/unlock',
    'command/v1/participant/unmute',
    'command/v1/conference/disconnect',
    'command/v1/conference/lock',
    'command/v1/conference/mute_guests',
    'command/v1/conference/send_conference_email',
    'command/v1/conference/send_device_email',
    'command/v1/conference/sync',
    'command/v1/conference/transform_layout',
    'command/v1/conference/unlock',
    'command/v1/conference/unmute_guests',
    'command/v1/platform/backup_create',
    'command/v1/platform/backup_restore',
    'command/v1/platform/certificates_import',
    'command/v1/platform/join_deployment',
    'command/v1/platform/promote_mgmtnode',
    'command/v1/platform/snapshot',
    'command/v1/platform/start_cloudnode',
]


class RestClient(CustomerMixin, LoginRequiredMixin, TemplateView):

    template_name = 'restclient/poster.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm('provider.api_client'):
            return HttpResponse(_('Access denied'), status_code=403)

        self.error = ''
        self.url = self.request.POST.get('url') or self.request.GET.get('url') or ''

        self.response = self._handle(request)

        return super().dispatch(request, *args, **kwargs)

    _rest_api = None
    def _get_api(self, force_reload=False, allow_cached_values=False):

        if self._rest_api and not force_reload:
            return self._rest_api

        def _cache(api):
            self._rest_api = api
            return api

        if not self.request.GET.get('provider'):
            return super()._get_api(force_reload=force_reload, allow_cached_values=allow_cached_values)

        api = self._get_dynamic_provider_api(allow_cached_values=allow_cached_values)[1]
        return _cache(api or self._get_customer().get_api())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['url'] = self.url
        context['method'] = self.request.POST.get('method') or self.request.GET.get('method')

        crumbs = []
        parts = context['url'].strip('/').split('/')
        for i in range(len(parts)):
            crumbs.append(['/'.join(parts[:i + 1]), parts[i]])

        context['crumbs'] = crumbs

        api = self._get_api()

        if self.request.POST.get('data'):
            context['args'] = self.get_args(self.request.POST.get('data'))

        if len(parts) > 1:

            context['subviews'], context['related'] = self.get_acano_subviews(parts)
            context['extra_base'] = '/'.join(parts[:2])

        context['data'] = self.request.POST.get('data') or ''
        context['error'] = self.error
        if self.response is not None:
            context['response'] = self.response

            if api.cluster.is_acano:
                context['xml'] = self.link_acano_objects(self.response.text)
            else:
                context['xml'] = self.link_pexip_objects(self.response.text)

            if self.response.headers.get('Location'):
                context['location'] = self.response.headers.get('Location').replace('/api/v1/', '').replace('/api/admin/', '')

                context['location_id'] = context['location'].strip('/').split('/')[-1]

        context['filters'], context['help'] = self.get_filters_and_help(self.request)
        if api.cluster.is_acano:
            context['urls'] = [(u, u) for u in URLS]
        else:
            context['urls'] = [(u + '/', u) for u in PEXIP_URLS]

        context['pagination'] = getattr(self, 'pagination', {})

        if api and api.customer and api.cluster.is_acano:
            context['tenants'] = [
                {
                    'id': c.acano_tenant_id,
                    'name': str(c),
                } for c in self._get_customers()
                if c.acano_tenant_id and c.lifesize_provider_id == api.cluster.pk
            ]
        if api and api.customer:
            context['provider'] = api.provider

        if self._has_all_customers():
            context['can_view_providers'] = True
            context['clusters'] = self.get_clusters()

        return context

    def get_acano_subviews(self, parts):
        subviews = []
        related_views = []

        if parts[0] == 'calls':
            subviews = ['callLegs', 'diagnostics', 'participants']
        elif parts[0].lower() == 'cospaces':
            subviews = ['accessMethods', 'coSpaceUsers', 'diagnostics', 'messages']
        elif parts[0].lower() == 'calllegs':
            subviews = ['callLegProfileTrace']
        elif parts[0].lower() == 'calllegprofiles':
            subviews = ['usage']
        elif parts[0].lower() == 'participants':
            subviews = ['callLegs']
        elif parts[0].lower() == 'users':
            subviews = ['usercoSpaces']
        elif parts[0].lower() in ('streamers', 'recorders', 'turnservers'):
            subviews = ['status']
        elif parts[0].lower() == 'webbridges':
            subviews = ['updateCustomization', 'status']
        elif parts[0].lower() == 'tenants':
            related_views = [
                    ('ldapSources/&tenantFilter=%s' % (parts[1]), 'ldapSources'),
                    ('coSpaces/&tenantFilter=%s' % (parts[1]), 'coSpaces'),
                    ('calls/&tenantFilter=%s' % (parts[1]), 'calls'),
                    ('users/&tenantFilter=%s' % (parts[1]), 'users'),
                    ]
        return subviews, related_views

    def get_filters_and_help(self, request, api=None):

        url = request.POST.get('url') or request.GET.get('url')
        if not url:
            return {}, {}

        api = api or self._get_api()
        if api.cluster.is_pexip:
            return self._get_pexip_filters_and_help(request, url, api)
        elif api.cluster.is_acano:
            return self._get_acano_filters_and_help(request)

    def _get_pexip_schema_url(self, url: str):
        without_query = url.split('?')[0]
        without_schema = re.sub(r'/schema/?$', '', without_query)
        without_pk = re.sub(r'/\d*/?$', '', without_schema)
        return '{}/schema/'.format(without_pk.rstrip('/'))

    def _get_pexip_filters_and_help(self, request, url, api):

        result = {}
        field_help = {}
        default_modifiers = ['exact', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith', 'endswith', 'iendswith', 'regex', 'iregex', 'lt', 'lte', 'gt', 'gte']

        try:
            schema = api.get(self._get_pexip_schema_url(url)).json()
            filtering = schema['filtering']
        except (ValueError, KeyError):
            schema = None
        else:
            for f, mods in filtering.items():
                result[f] = {
                    'value': request.POST.get('f_' + f) or request.GET.get('f_' + f) or '',
                    'mod': request.POST.get('mod_' + f) or request.GET.get('mod_' + f) or '',
                    'help_text': schema['fields'].get(f, {}).get('help_text', ''),
                    'mods': default_modifiers if isinstance(mods, int) else mods,
                }

            for f, info in schema.get('fields', {}).items():
                cur = []
                if info.get('blank'):
                    cur.append('blank')
                if info.get('nullable'):
                    cur.append('nullable')
                if info.get('type'):
                    cur.append('type: {}'.format(info['type']))

                field_help[f] = '{}: {}'.format(info.get('help_text', '').strip('.'), ', '.join(cur)).strip(':')

        return result, field_help

    def _get_acano_filters_and_help(self, request):
        filters = ['filter', 'tenantFilter', 'offset', 'limit', 'customer', 'callLegProfileFilter', 'usageFilter']

        result = {}

        for f in filters:
            result[f] = {
                'value': request.POST.get(f) or request.GET.get(f) or '',
                'mod': '',
                'hidden': f not in ('filter', 'tenantFilter'),
            }

        return result, {}

    def _handle(self, request):

        self.pagination = {}

        url = request.POST.get('url') or request.GET.get('url')
        method = request.POST.get('method') or request.GET.get('method') or 'GET'

        if not url or not method or method == "TEST":
            return None

        api = self._get_api()

        if api.cluster.is_acano:
            args = self.get_args(request.POST.get('data'))
        else:
            args = request.POST.get('data', '{}')
            if args:
                try:
                    json.loads(args)
                except ValueError as e:
                    self.error = 'JSON Error, not sent to server: {}'.format(e)
                    return

        filters, help = self.get_filters_and_help(request, api=api)

        params = {'{}__{}'.format(k, v['mod']) if v['mod'] and v['mod'] != 'exact' else k: v['value'] for k, v in filters.items() if v['value']}
        try:
            response = api.request(url, data=args, params=params, method=method)
        except ResponseError as e:
            response = e.args[1]

        if response.status_code == 200 and response.text.startswith('<'):
            self.handle_acano_pagination_result(response, filters)

        self.url = url
        return response

    def handle_acano_pagination_result(self, response, filters):
        node = safe_xml_fromstring(response.text)
        total = node.get('total')

        if not total or total == '0':
            return

        limit = int(filters.get('limit', {}).get('value') or 0)
        offset = int(filters.get('offset', {}).get('value') or 0)

        total = int(total)
        pages = total // (limit or len(node))
        page = offset // (limit or len(node)) + 1

        next_page = self.request.GET.copy()
        next_page.update({
            'limit': limit or len(node),
            'offset': offset + len(node),
        })

        next_page['url'] = '?%s' % urllib.parse.urlencode(next_page)

        prev_page = self.request.GET.copy()
        prev_page.update({
            'limit': limit or len(node),
            'offset': offset - (limit or len(node)),
        })

        prev_page['url'] = '?%s' % urllib.parse.urlencode(prev_page)

        self.pagination = {
            'next': next_page,
            'prev': prev_page,
            'page': page,
            'pages': pages,
        }

    def get_args(self, data):
        data = (data or '')

        data = re.sub(r'^\s*<([A-z0-9]+)>([^<]*)</\1>\s*$', r'\1=\2', data, 0, re.MULTILINE)
        data = re.sub(r'^\s*<([A-z0-9]+)>([^<]*)\s*$', r'\1=\2', data, 0, re.MULTILINE)
        data = data.split('\n')

        lines = [l.strip().split('=', 1) for l in data if '=' in l]
        args = {l[0].strip(): l[1].strip() for l in lines}

        return args

    def link_acano_objects(self, xml):

        from xml.sax.saxutils import escape  # qa: ignore S406
        text = escape(prettify_xml(xml))

        regexps = [
            ('userCoSpace', r'((userCoSpace) id="(.*?)")'),
            ('system/cdrReceivers', r'((cdrReceiver) id="(.*?)")'),
            ('/'.join(self.url.split('/')[:3]), r'((coSpaceUser|userCoSpace|accessMethod) id="(.*?)")'),
            ('', r'((?<![>])&lt;([A-z]+) id="(.*?)")'),
            ('', r'(&lt;(coSpace|callBridge|call|tenant|ldapServer)&gt;([^\&]+)&lt;/)'),
            ('', r'(&lt;((?:call|callLeg|callBranding|ivrBranding|dtmfProfile)Profile)&gt;([^\&]+)&lt;/)'),
            ('coSpaces', r'(&lt;(coSpaceId)&gt;([^\&]+)&lt;/)'),
            ('users', r'(&lt;(userId)&gt;([^\&]+)&lt;/)'),
            ('ldapMappings', r'(&lt;(mapping)&gt;([^\&]+)&lt;/)'),
            ('ldapServers', r'(&lt;(server)&gt;([^\&]+)&lt;/)'),
        ]

        api = self._get_api()
        customer = api.customer

        for prefix, regexp in regexps:
            for m in re.findall(regexp, text):
                p = m[1] + 's' if not prefix else prefix
                url = p + '/' + m[2]

                text = text.replace(m[0], '<a href="?url=%s&amp;customer=%s&amp;provider=%s">%s</a>' % (url, customer.pk, api.provider.pk, m[0]))

        return text

    def link_pexip_objects(self, data):

        try:
            text = json.dumps(json.loads(data), indent=2)
        except ValueError:
            text = data

        api = self._get_api()

        for urls in re.findall(r'("/api/admin/([^"]+)")', text):
            text = text.replace(urls[0], '<a href="?url={}&amp;provider={}">{}</a>'.format(urls[1], api.provider.pk, urls[0]))
        return text

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def get_clusters(self):
        clusters = []

        done = set()
        for provider in Provider.objects.filter(type=Provider.TYPES.lifesize):
            if not (provider.is_pexip or provider.is_acano) or provider.pk in done:
                continue

            cur = provider.get_clustered(include_self=True)
            done.update(p.pk for p in cur)

            clusters.append([p for p in cur if not p.is_cluster])
        return clusters


