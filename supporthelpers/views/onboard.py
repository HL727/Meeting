from typing import List, Optional
from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, CreateView, TemplateView
from django.utils.translation import gettext as _

from customer.models import Customer
from provider.models.provider import Cluster, Provider
from provider.models.vcs import VCSEProvider
from shared.models import GlobalOptions
from shared.onboard import init_db
from supporthelpers.forms import (
    BasicSetupForm,
    AcanoSetupForm,
    ExtendAcanoClusterForm,
    VCSSetupForm,
    PexipSetupForm,
    NewClusterSetupForm,
    NewCallControlClusterSetupForm,
)
from supporthelpers.views.mixins import SettingsProductMixin


def get_setup_view(request, only_key=None):

    has_users = User.objects.exclude(username='mividas_fallback', password='').exists()

    if has_users and not (request.user.is_authenticated and request.user.is_staff):
        return

    if not Customer.objects.exclude(id=1, title=''):
        if not only_key or only_key == 'onboard_setup':
            return 'onboard_setup'

    if not only_key and request.user.is_staff:
        # Return to start if this is not pre-install onboarding wizard
        if settings.ENABLE_CORE:
            return 'provider_dashboard'
        return ''

    if (
        settings.ENABLE_CORE
        and not GlobalOptions.objects.get_or_create(option='skip_cluster')[0].value
    ):
        if not only_key or only_key == 'onboard_cluster':
            return 'onboard_cluster'

        cluster_type = request.session.get('onboard_cluster') or ''

        if cluster_type == 'acano' and only_key == 'onboard_acano':
            if not GlobalOptions.objects.get_or_create(option='skip_acano')[0].value:
                return 'onboard_acano'
        if cluster_type == 'pexip' and only_key == 'onboard_pexip':
            if not GlobalOptions.objects.get_or_create(option='skip_pexip')[0].value:
                return 'onboard_pexip'
        if cluster_type == 'acano' and request.session.get('has_more_acano'):
            if not only_key or only_key == 'onboard_acano_extra':
                if not GlobalOptions.objects.get_or_create(option='skip_acano')[0].value:
                    return 'onboard_acano_extra'

    if (
        settings.ENABLE_CORE
        and not GlobalOptions.objects.get_or_create(option='skip_cluster_call_control')[0].value
    ):
        if not only_key or only_key == 'onboard_cluster_callcontrol':
            return 'onboard_cluster_callcontrol'

        call_control_type = request.session.get('onboard_cluster_callcontrol')

        if call_control_type == 'vcs' and only_key == 'onboard_vcs':
            if not GlobalOptions.objects.get_or_create(option='skip_vcs')[0].value:
                return 'onboard_vcs'

    if not has_users:
        if not only_key or only_key == 'onboard_fallback_password':
            return 'onboard_fallback_password'
    return None


class OnboardStepMixin(View):

    onboard_view_name: str = ''
    onboard_skip_next_url: Optional[str] = None
    onboard_skip_names: List[str] = []

    def dispatch(self, request, *args, **kwargs):

        if not get_setup_view(request, self.onboard_view_name) and not request.user.is_staff:
            return redirect(get_setup_view(self.request) or '/')

        if request.GET.get('skip'):
            request.session.pop('onboard_cluster', None)

            for skip_name in self.onboard_skip_names:
                GlobalOptions.objects.update_or_create(option=skip_name, defaults={'value': True})
            if self.onboard_skip_next_url:
                return redirect(self.onboard_skip_next_url)
            return redirect(get_setup_view(self.request) or '/')

        return super().dispatch(request, *args, **kwargs)


class OnboardUseClusterMixin(FormView):
    def dispatch(self, request, *args, **kwargs):

        if not get_setup_view(request) and not request.user.is_staff:
            return redirect(get_setup_view(request) or '/')

        cluster = self._init_cluster(**kwargs)
        if isinstance(cluster, HttpResponse):
            return cluster

        return super().dispatch(request, *args, **kwargs)

    def _init_cluster(self, **kwargs):
        try:
            if kwargs.get('cluster_id'):
                self.cluster = Cluster.objects.get(pk=kwargs['cluster_id'])
        except (Cluster.DoesNotExist, Cluster.MultipleObjectsReturned):
            return redirect('/')

    def get_form_kwargs(self, **kwargs):
        result = super().get_form_kwargs()
        result['override_cluster'] = self.cluster
        return result


class OnboardCreateMixin(SettingsProductMixin, OnboardStepMixin, CreateView):
    pass


class OnboardCreateProviderMixin(
    SettingsProductMixin, OnboardStepMixin, OnboardUseClusterMixin, CreateView
):

    pass


class SetFallbackPasswordView(SettingsProductMixin, OnboardStepMixin, FormView):

    form_class = SetPasswordForm
    template_name = 'setup/fallback_password.html'

    onboard_view_name = 'onboard_fallback_password'
    onboard_skip_next_url = '/accounts/login/?force=1'
    onboard_skip_names = ['skip_fallback_user']

    def get_form_kwargs(self, **kwargs):
        user = User.objects.filter(username='mividas_fallback', password='').first()
        return {**super().get_form_kwargs(), 'user': user}

    def form_valid(self, form):
        user = form.save()

        user = authenticate(
            request=self.request,
            username=user.username,
            password=form.cleaned_data['new_password1'],
            backend=settings.AUTHENTICATION_BACKENDS[-1],
        )
        login(self.request, user)
        return redirect(get_setup_view(self.request) or '/')


class BasicSettingsView(SettingsProductMixin, FormView):

    def dispatch(self, request, *args, **kwargs):
        if not get_setup_view(request, 'onboard_setup'):
            return redirect(get_setup_view(self.request) or '/')

        init_db()
        return super().dispatch(request, *args, **kwargs)

    template_name = 'setup/onboard.html'
    form_class = BasicSetupForm

    def form_valid(self, form):

        form.save()
        return redirect(get_setup_view(self.request) or '/')


class NewClusterSetup(OnboardCreateMixin):

    template_name = 'setup/cluster.html'
    form_class = NewClusterSetupForm

    onboard_view_name = 'onboard_cluster'
    onboard_skip_names = ['skip_cluster']

    def get_initial(self):
        return self.request.GET

    def get_context_data(self, **kwargs):
        cluster_done = self.request.session.pop('onboard_cluster_done', None)
        return {
            **super().get_context_data(),
            'button_text': _('Fortsätt till anslutningsuppgifter'),
            'cluster_done': cluster_done if get_setup_view(self.request) else False,
            'simple_mode': not settings.ENABLE_CORE,
        }

    def form_valid(self, form):
        form.save()

        if form.cleaned_data.get('type') == Cluster.TYPES.acano_cluster:
            self.request.session['onboard_cluster'] = 'acano'
            return redirect(reverse('onboard_acano', args=[form.instance.pk]))
        elif form.cleaned_data.get('type') == Cluster.TYPES.pexip_cluster:
            self.request.session['onboard_cluster'] = 'pexip'
            return redirect(reverse('onboard_pexip', args=[form.instance.pk]))
        return redirect(get_setup_view(self.request) or '/')


class NewCallControlClusterSetup(OnboardCreateMixin):

    template_name = 'setup/cluster_callcontrol.html'
    form_class = NewCallControlClusterSetupForm

    onboard_view_name = 'onboard_cluster_callcontrol'
    onboard_skip_names = ['skip_cluster_call_control']

    def get_initial(self):
        return self.request.GET

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(),
            'button_text': _('Fortsätt till anslutningsuppgifter'),
        }

    def form_valid(self, form):
        form.save()

        if form.cleaned_data.get('type') == Cluster.TYPES.vcs_cluster:
            self.request.session['onboard_cluster_callcontrol'] = 'vcs'
            return redirect(reverse('onboard_vcs', args=[form.instance.pk]))
        return redirect(get_setup_view(self.request) or '/')


class AcanoSetup(OnboardCreateProviderMixin):

    template_name = 'setup/acano.html'
    form_class = AcanoSetupForm

    onboard_view_name = 'onboard_acano'
    onboard_skip_names = ['skip_acano']

    def dispatch(self, request, *args, **kwargs):
        self.request.session['has_more_acano'] = True

        if request.GET.get('skip'):
            request.session.pop('has_more_acano', None)

        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return self.request.GET

    def form_valid(self, form):
        try:
            form.validate_login()
        except forms.ValidationError:
            return self.form_invalid(form)

        instance = form.save()

        if ExtendAcanoSetupView.get_servers_to_add(instance).get('call_bridges'):
            self.request.session['has_more_acano'] = True
            return redirect('onboard_acano_extra', instance.cluster_id or instance.pk)

        self.request.session.pop('onboard_cluster', None)
        self.request.session['onboard_cluster_done'] = True
        return redirect(get_setup_view(self.request) or '/')


class ExtendAcanoSetupView(
    SettingsProductMixin, OnboardStepMixin, OnboardUseClusterMixin, TemplateView
):

    template_name = 'setup/acano_extra.html'
    form_class = ExtendAcanoClusterForm

    onboard_view_name = 'onboard_acano_extra'
    onboard_skip_names = ['skip_acano']

    def dispatch(self, request, *args, **kwargs):
        if not get_setup_view(request, self.onboard_view_name) and not request.user.is_staff:
            return redirect(get_setup_view(self.request) or '/')

        if request.GET.get('skip'):
            return super().dispatch(request, *args, **kwargs)

        self._init_cluster(**kwargs)

        if not self.cluster.get_clustered(only_call_bridges=False):
            return redirect('onboard_acano', self.cluster.pk)

        self.servers_to_add = self.get_servers_to_add(self.cluster)
        self.form_i = 0

        return super().dispatch(request, *args, **kwargs)

    def get_extend_form(self, initial):
        self.form_i += 1
        return ExtendAcanoClusterForm(initial=initial,
                                      data=self.request.POST if self.request.POST else None,
                                      override_cluster=self.cluster,
                                      prefix='form{}'.format(self.form_i))

    def get(self, request, *args, **kwargs):

        self.forms = [self.get_extend_form(cb) for cb in self.servers_to_add['call_bridges']]
        if not self.forms:
            self.forms = [self.get_extend_form(s) for s in self.servers_to_add['service_nodes']]

        if not self.forms:
            self.forms = [self.get_extend_form({})]

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):

        self.forms = [self.get_extend_form(cb) for cb in self.servers_to_add['call_bridges']]
        if not self.forms:
            self.forms = [self.get_extend_form(s) for s in self.servers_to_add['service_nodes']]
        if not self.forms:
            self.forms = [self.get_extend_form({})]

        error = False
        valid = 0
        for f in self.forms:
            if not f.is_valid():
                error = True
                continue

            try:
                f.validate_login()
            except forms.ValidationError:
                error = True
                continue

            f.save()
            valid += 1

        if error:
            return self.render_to_response(self.get_context_data(valid=valid))

        self.request.session.pop('has_more_acano', None)
        self.request.session.pop('onboard_cluster', None)
        self.request.session['onboard_cluster_done'] = True
        return redirect(get_setup_view(self.request) or '/')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['existing'] = Provider.objects.filter(subtype=Provider.SUBTYPES.acano).order_by('id').first()
        context['auto_add'] = any(x for x in self.servers_to_add.values())
        context['forms'] = self.forms
        context['button_text'] = None

        return context

    @staticmethod
    def get_servers_to_add(provider):
        customer = Customer.objects.first()

        existing = {p.get_api(customer).get_call_bridge_id() for p in provider.get_clustered(include_self=True)}
        all_servers = provider.get_api(customer).get_all_clustered_servers()

        add = {
            'call_bridges': [],
            'service_nodes': [],
        }

        def _ip_host(s):
            hostname = urlparse(s).hostname if '/' in s else s
            ip = ''

            if hostname.replace('.', '').isdigit():  # is ip
                ip, hostname = hostname, ''

            return {
                'hostname': hostname,
                'ip': ip,
            }

        already_in_add = {host for p in provider.get_clustered(include_self=True) for host in (p.ip, p.hostname)}

        for bridge in all_servers['call_bridges']:
            bridge.setdefault('address', '')
            url = urlparse(bridge['address'])

            cur = {
                'title': bridge['name'],
                **_ip_host(bridge['address']),
                'api_host': url.netloc if url.netloc != url.hostname else '',
            }
            already_in_add.update({cur['ip'], cur['hostname']})
            if bridge['id'] not in existing:
                add['call_bridges'].append(cur)

        def _add_service(title, url):
            cur = {
                'title': title,
                **_ip_host(url),
                'is_service_node': True,
            }
            if {cur['ip'], cur['hostname']} & (already_in_add - {''}):
                return
            already_in_add.update({cur['ip'], cur['hostname']})
            add['service_nodes'].append(cur)

        for i, db in enumerate(all_servers.get('database') or []):
            _add_service('db{}'.format(i + 1), db['hostname'])

        for i, streamer in enumerate(all_servers.get('streamers') or []):
            _add_service('streamer{}'.format(i + 1), streamer['url'])

        for i, recorder in enumerate(all_servers.get('recorders') or []):
            _add_service('recorder{}'.format(i + 1), recorder['url'])

        return add


class PexipSetup(OnboardCreateProviderMixin):

    template_name = 'setup/pexip.html'
    form_class = PexipSetupForm

    onboard_view_name = 'onboard_pexip'
    onboard_skip_names = ['skip_pexip']

    def get_initial(self):
        return self.request.GET

    def form_valid(self, form):
        try:
            form.validate_login()
        except forms.ValidationError:
            return self.form_invalid(form)

        form.save()

        self.request.session.pop('onboard_cluster', None)
        self.request.session['onboard_cluster_done'] = True
        return redirect(get_setup_view(self.request) or '/')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['existing'] = Provider.objects.filter(subtype=Provider.SUBTYPES.pexip).order_by('id').first()
        return context


class VCSSetup(OnboardCreateProviderMixin):

    template_name = 'setup/vcs.html'
    form_class = VCSSetupForm

    onboard_view_name = 'onboard_vcs'
    onboard_skip_names = ['skip_vcs']

    def get_initial(self):
        return self.request.GET

    def form_valid(self, form):
        try:
            form.validate_login()
        except forms.ValidationError:
            return self.form_invalid(form)

        customers = list(Customer.objects.all())
        instance = form.save()
        if len(customers) == 1 and not customers[0].lifesize_provider_id:
            instance.customer = customers[0]
            instance.save()

        self.request.session.pop('onboard_cluster', None)
        return redirect(get_setup_view(self.request) or '/')


def settings_list(request):
    if not request.user.is_staff:
        return HttpResponse(status_code=403)

    from endpoint.models import CustomerSettings
    epm_customers = []
    for c in Customer.objects.filter(enable_epm=True):
        epm_customers.append((c, CustomerSettings.objects.get_for_customer(c)))

    from statistics.models import Server
    servers = []
    for server in Server.objects.exclude(type__in=(Server.ENDPOINTS, Server.COMBINE)):
        servers.append(server)

    data = {
            'epm_customers': epm_customers,
            'stat_servers': servers,
            'customers': Customer.objects.all(),
            }

    return render(request, 'setup/settings_list.html', data)




