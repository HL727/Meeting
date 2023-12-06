from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import views as auth
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.views import PasswordChangeView
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.timezone import localtime
from django.views.generic import TemplateView
from sentry_sdk import capture_exception

from theme.utils import get_theme_settings
from .mixins import SettingsProductMixin
from customer.view_mixins import LoginRequiredMixin, CustomerMixin
from .onboard import get_setup_view
from ..forms import MeetingFilterForm


class IndexView(LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'base_vue.html'

    def get(self, request, *args, **kwargs):

        # allow counters even if core is disabled for now until enable_core flag is working in admin
        if request.GET.get('get_counters'):
            return JsonResponse(self.get_counters())

        if not settings.ENABLE_CORE or (self.customer and not self.customer.enable_core):
            if settings.ENABLE_EPM:
                return redirect(
                    '{}://{}/epm/'.format(
                        request.scheme if settings.DEBUG else 'https', settings.HOSTNAME
                    )
                )

        if settings.EPM_HOSTNAME != settings.HOSTNAME:
            if request.META.get('HTTP_HOST', '').split(':')[0] == settings.EPM_HOSTNAME:
                return HttpResponse('Only events from video conference systems are allowed on this domain')

        return super().get(request, *args, **kwargs)

    def get_counters(self, customer=None):
        from meeting.models import Meeting
        from provider.exceptions import ResponseError, AuthenticationError
        from django.utils.timezone import now
        from statistics.forms import StatsForm
        from statistics.models import Server

        if not customer:
            try:
                customer = self._get_customer() or self._get_customers()[0]
            except IndexError:
                return {}

        if not customer.get_provider():
            return {}
        try:
            api = customer.get_api(allow_cached_values=True)
            tenant_id = customer.tenant_id

            seconds = 0
            call_count = 0
            stats_link = None

            servers = Server.objects.filter_for_customer(customer)
            for server in servers:
                stats_filter = {
                    'ts_start': localtime().replace(hour=0, minute=0, second=0),
                    'ts_stop': localtime(),
                    'server': server.pk,
                }

                form = StatsForm(stats_filter, user=self.request.user, customer=customer)
                if not form.is_valid():  # ignore endpoint server types etc
                    continue
                calls = form.get_calls()

                seconds += sum(c.total_duration for c in calls if c.total_duration >= 60)
                call_count += calls.count()

                if not stats_link:
                    stats_link = '{}?{}'.format(
                        reverse('stats'),
                        urlencode(
                            {
                                'ts_start': stats_filter['ts_start'].isoformat(),
                                'ts_stop': stats_filter['ts_stop'].isoformat(),
                            }
                        ),
                    )


            meetings = MeetingFilterForm(
                {'only_active': True, 'ts_start': now()}, user=self.request.user, customer=customer
            ).get_meetings()

            result = {
                'upcoming_meetings_count': meetings.count(),
                'today_hours': int(seconds / 60 / 60),
                'today_calls': call_count,
                'stats_link': stats_link,
            }
            try:
                tenant_kwargs = {'tenant': tenant_id or '', 'limit': 1}
                if api.cluster.is_acano and not tenant_id and not self._has_all_customers():
                    tenant_kwargs.pop('limit', None)  # no default tenant filter. iter everything

                result.update({
                    'cospace_count': api.find_cospaces('', **tenant_kwargs)[1],
                    'user_count': api.find_users('', **tenant_kwargs)[1],
                    'active_meetings_calls': api.get_clustered_calls(tenant=tenant_id or '')[1],
                    'active_meetings_legs': api.get_clustered_participants(tenant=tenant_id or '')[1],
                })
            except (ResponseError, AuthenticationError) as e:
                result['error'] = str(e)

            return result

        except Exception as e:
            if settings.DEBUG:
                raise
            else:
                capture_exception()
            return {'error': str(e)}


class LoginView(SettingsProductMixin, auth.LoginView):

    template_name = 'login.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['theme'] = get_theme_settings()
        return context

    def get(self, request, *args, **kwargs):
        force_login = request.GET.get('force')

        setup_view = get_setup_view(request)
        if setup_view:
            if not (setup_view == 'onboard_fallback_password' and force_login):
                return redirect(setup_view)

        return super().get(request, *args, **kwargs)


class ChangePasswordView(PasswordChangeView):

    template_name = 'users/change_password.html'
    success_url = '/'

    def dispatch(self, request, *args, **kwargs):
        if settings.LDAP_SERVER:
            return HttpResponse('Password change is not available for LDAP-users')
        return super().dispatch(request, *args, **kwargs)
