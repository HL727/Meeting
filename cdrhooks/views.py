from django.views.generic import TemplateView
from django.shortcuts import redirect
from provider.forms import CoSpaceForm


from django.utils.translation import ugettext_lazy as _

from .forms import HookForm, DialoutForm
from .models import Dialout, Hook, Session
from customer.view_mixins import LoginRequiredMixin, CustomerMixin


class HookFormView(LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'cdrhooks/cospace.html'

    def _get_cospace(self):
        cospace_id = self.kwargs.get('cospace_id') or self.request.GET.get('cospace')

        if cospace_id:
            return CoSpaceForm(cospace=cospace_id).load(customer=self._get_customer(self.request))
        return {}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self._get_customer(self.request)

        if customer:
            context['customer'] = customer
            provider = customer.get_provider()
            assert provider.is_acano

            cospace = self._get_cospace()

            context['cospace'] = cospace

            try:
                hook = Hook.objects.get(provider=provider, provider_ref=cospace['cospace'])
            except Hook.DoesNotExist:
                hook = None
            else:
                context['dialouts'] = Dialout.objects.filter(hook=hook)
                context['sessions'] = hook.get_sessions()
                context['hook'] = hook

            if 'hook_form' not in context:
                context['hook_form'] = HookForm(cospace=cospace['cospace'], customer=customer)

            if 'dialout_form' not in context:
                context['dialout_form'] = DialoutForm()

            from cdrhooks.models import ScheduledDialout
            context['scheduled_dialouts'] = ScheduledDialout.objects.get_active(provider, cospace['cospace'])

        if not context.get('error'):
            context['message'] = self.request.session.pop('cospaces_message', None)

        return context

    def post(self, request, *args, **kwargs):

        cospace = self._get_cospace()
        customer = self._get_customer(self.request)

        if request.POST.get('form_action') == 'edit_hook':
            hook_form = HookForm(request.POST, cospace=cospace['cospace'], customer=customer)

            errors = not hook_form.is_valid()

            hook = None
            if not errors:
                hook = hook_form.save()

            dialout_form = DialoutForm(request.POST, hook=hook)

            if request.POST.get('dialstring'):
                errors = not dialout_form.is_valid() or errors

                if not errors and dialout_form.is_valid():
                    dialout_form.save()

            if errors:
                return self.render_to_response(self.get_context_data(hook_form=hook_form, dialout_form=dialout_form, error=errors))

        elif request.POST.get('form_action') == 'remove_dialout':
            Dialout.objects.filter(hook__provider_ref=cospace['cospace'], hook=request.POST.get('hook'), pk=request.POST.get('dialout')).delete()

        elif request.POST.get('form_action') == 'disconnect_session':
            try:
                hook = Hook.objects.get(pk=request.POST.get('hook'), provider_ref=cospace['cospace'])
                hook.get_sessions().get(pk=request.POST.get('session')).deactivate()
            except (Hook.DoesNotExist, Session.DoesNotExist):
                pass

        request.session['cospaces_message'] = str(_('Åtgärden slutfördes utan problem'))
        return redirect(request.get_full_path())


