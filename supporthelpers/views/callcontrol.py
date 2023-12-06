import json

from django.views.generic import TemplateView
from django.shortcuts import redirect

from statistics.models import Call
from ..models import DialoutHistory
from django.urls import reverse
from django.http import HttpResponse
from provider.exceptions import NotFound
from django.utils.timezone import now


from django.utils.translation import ugettext_lazy as _

from meeting.models import Meeting
from provider.exceptions import ResponseError
from datetime import timedelta

from customer.view_mixins import LoginRequiredMixin, CustomerMixin


class CallHandler(LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'callcontrol/call.html'

    def dispatch(self, request, *args, **kwargs):
        try:
            call = self._get_call()
        except Exception:
            call = None
        if not call:
            return redirect('calls')

        self.call = call

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):

        if request.GET.get('ajax'):
            history = DialoutHistory.objects.filter(user=self.request.user)[:5]
            history_json = json.dumps([{'id': x.id, 'uri': x.uri, 'name': x.name} for x in history])

            return HttpResponse(json.dumps(history_json), content_type='text/json')

        return super().get(request, *args, **kwargs)

    def _get_clustered_call(self):
        customer = self._get_customer(self.request)

        try:
            for call, api in customer.get_api().get_clustered_call(self.kwargs.get('call_id')):
                self.customer = self._check_tenant_customer(call.get('tenant'), change=True)
                return call, api
        except NotFound:
            return None, None

    def _get_call(self):
        return self._get_clustered_call()[0]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self._get_customer(self.request)

        if not customer:
            return context

        context['customer'] = customer
        provider = customer.get_provider()
        assert provider.is_acano
        context['provider'] = provider

        call = self.call

        api = self._get_api(allow_cached_values=True)

        context['call'] = call
        context['duration'] = timedelta(seconds=call['duration'])
        try:
            cospace = api.get_cospace(call['cospace'])
            context['cospace'] = cospace
            context['sip_uri'] = api.get_sip_uri(cospace=cospace)
            context['web_url'] = api.get_web_url(cospace=cospace)
        except Exception:
            context['cospace'] = {'name': 'Unspecified cospace'}

        history = DialoutHistory.objects.filter(user=self.request.user)[:10]
        context['history_json'] = json.dumps([{'id': x.id, 'uri': x.uri, 'name': x.name} for x in history])

        context['is_recording'] = call.get('recording') or (call.get('streaming') and not customer.streaming_provider_id)

        if not context.get('error'):
            context['message'] = self.request.session.pop('cospaces_message', None)

        recording_provider = customer.get_videocenter_provider()
        if recording_provider:
            context['recording_host'] = recording_provider.hostname or recording_provider.ip
            context['recording_provider'] = recording_provider

        from cdrhooks.models import ScheduledDialout
        context['scheduled_dialouts'] = ScheduledDialout.objects.get_active(provider, call['cospace'])
        context['layout_choices'] = Meeting.ACANO_LAYOUT_CHOICES
        context['layout_choices_json'] = json.dumps({ k: str(v) for k, v in Meeting.ACANO_LAYOUT_CHOICES})

        context['request'] = self.request

        if customer:
            call_ids = [c['id'] for c, p in customer.get_api().get_clustered_call(self.kwargs.get('call_id'))]
        else:
            call_ids = [call['id']]

        all_calls = Call.objects.filter(ts_start__gt=now() - timedelta(hours=10), guid__in=call_ids).order_by('-ts_start')
        context['latest_calls'] = all_calls

        return context

    def post(self, request, *args, **kwargs):

        uri = request.POST.get('uri')
        recording_key = request.POST.get('recording_key')
        layout = request.POST.get('layout')
        remove_scheduled_dialout = request.POST.get('remove_scheduled_dialout')
        silent = request.POST.get('silent')

        call_id = self._get_call()['id']

        if uri:
            try:
                self._dialout(request, uri, layout=layout, silent=silent)
            except ResponseError:
                context = self.get_context_data(error=_('Kunde inte ringa upp externt system. Kontrollera så adressen inte pekar på en intern användare'))
                return self.render_to_response(context)
        elif request.POST.get('start_stream'):
            self._get_customer().get_streaming_api().adhoc_record(self._get_api(), call_id, recording_key=recording_key)
        elif request.POST.get('stop_stream'):
            self._get_customer().get_streaming_api().adhoc_stop_record(self._get_api(), call_id)
        elif request.POST.get('stop_recording'):
            self._get_customer().get_recording_api().adhoc_stop_record(self._get_api(), call_id)
        elif recording_key:
            self._record(request, recording_key, layout=layout, silent=silent)
        elif remove_scheduled_dialout:
            from cdrhooks.models import ScheduledDialout
            try:
                ScheduledDialout.objects.get(pk=remove_scheduled_dialout).unschedule()
            except ScheduledDialout.DoesNotExist:
                pass
        elif request.POST.get('delete_call'):
            cospace = self._get_call()['cospace']
            for call, api in self._get_customer().get_api().get_clustered_call(call_id):
                api.hangup_call(call['id'])
            return redirect(reverse('cospaces_details', args=[cospace]) + '?customer={}&cospace={}'.format(self._get_customer().pk, cospace))

        return redirect(request.get_full_path())

    def _set_layout(self, leg_id, layout):
        self._get_api().update_call_leg(leg_id, {
            'chosenLayout': layout,
        })

    def _mute(self, leg_id, mute=True):

        self._get_api().update_call_leg(leg_id, {
            'rxAudioMute': 'true' if mute else 'false',
        })

    def _dialout(self, request, uri, layout=None, silent=False):

        if silent:
            call_leg_profile = self._get_customer().get_api()._get_webinar_call_legs(force_encryption=False)[0]
        else:
            call_leg_profile = None

        if uri:

            call, api = self._get_clustered_call()
            if call:
                DialoutHistory.objects.add(request.user, uri, request.POST.get('name'))
                api.add_participant(call['id'], uri, layout=layout, call_leg_profile=call_leg_profile)
                request.session['cospaces_message'] = str(_('Systemet försöker ringa upp deltagaren'))

    def _record(self, request, recording_key, layout=None, silent=False):

        call = self._get_call()
        provider = self._get_customer().get_videocenter_provider()

        if not (call and provider and self._get_api().provider.is_acano):
            return

        provider.get_api(self._get_customer()).adhoc_record(self._get_api(), call['id'], layout=layout, recording_key=recording_key, silent=bool(silent))

