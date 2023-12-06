from django.core.exceptions import ValidationError
from django.shortcuts import redirect, get_object_or_404
from django.utils.translation import ugettext as _
from django.http import HttpResponse
from .models import DefaultMessage, Message, String
from django.contrib.auth.decorators import login_required
from django.urls import reverse
import json
from sentry_sdk import capture_message

import reversion

from django.views.generic import TemplateView
from customer.view_mixins import LoginRequiredMixin, CustomerMixin


class ListCustomers(LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'message/list_customers.html'

    def get(self, request, *args, **kwargs):
        customers = self._get_customers()
        if len(customers) == 1:
            return redirect(reverse('list_messages', args=[customers[0].pk]))

        return super().get(request, *args, **kwargs)


class MessagesMixin:

    def _get_customer(self, request=None, customer_id=None):

        customer_id = customer_id or self.kwargs.get('customer_id')
        if customer_id == 'default':
            return None
        if self.kwargs.get('current_customer'):
            customer_id = None

        return super()._get_customer(request=request, customer_id=customer_id)

    def _get_messages(self):
        return Message.objects.get_all(self._get_customer())

    def _get_strings(self):
        # deprecated
        result = String.objects.get_all(self._get_customer())
        if any(s.title for s in result):
            return result
        return []  # disabled for new installations

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context.update({
            'messages': self._get_messages(),
            'strings': self._get_strings(),
        })

        return context


class UpdateMessageView(LoginRequiredMixin, MessagesMixin, CustomerMixin, TemplateView):

    template_name = 'message/update.html'

    def _update_message(self, pk, title, content, customer=None):

        request = self.request

        default = request.POST.get('default_message%s' % pk)

        if customer:
            try:
                msg = Message.objects.get(pk=pk, customer=customer)
            except Message.DoesNotExist:
                pass
            else:  # set default message if empty
                if not content:
                    content = Message.objects.get_by_type(msg.type, None).content
                if not title:
                    title = Message.objects.get_by_type(msg.type, None).title

        message_objects = Message.objects.filter(pk=pk, customer=customer)
        message_objects.update(title=title, content=content, active=not customer or not default)

        msg = message_objects.first()

        allow_attachment = bool(msg.attachment)

        delete_attachment = request.POST.get('delete_attachment_{}'.format(pk))
        attachment = request.FILES.get('attachment_{}'.format(pk)) or None
        if delete_attachment:
            msg.attachment.delete()
        elif attachment and allow_attachment:
            msg = msg
            msg.attachment = attachment
            try:
                msg.full_clean()
            except ValidationError:
                self.request.session['message_save_error'] = _(
                    'Filen kunde inte sparas. Använd ett annat format'
                )
            else:
                msg.save()

    @reversion.create_revision()
    def post(self, request, *args, **kwargs):

        ids = request.POST.getlist('message_id')
        titles = request.POST.getlist('message_title')
        contents = request.POST.getlist('message_content')

        customer = self._get_customer()

        for pk, title, content in zip(ids, titles, contents):

            self._update_message(pk, title, content, customer=customer)
            request.session['ui_messages.edited'] = True

        ids = request.POST.getlist('string_id')
        titles = request.POST.getlist('string_title')

        for pk, title in zip(ids, titles):

            if not request.user.is_staff:  # only staff
                break

            default = request.POST.get('default_string%s' % pk)
            String.objects.filter(pk=pk, customer=customer).update(title=title, active=not customer or not default)

            request.session['ui_messages.edited'] = True

        if customer:
            customer.has_custom_messages = Message.objects.filter(customer=customer, active=True).count() > 0
            customer.save()
            return redirect('list_messages', customer.pk)
        return redirect('list_messages', 'default')

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        customer = self._get_customer()

        context.update(
            {
                'updated': self.request.session.pop('ui_messages.edited', False),
                'error': self.request.session.pop('message_save_error', None),
                'placeholders': Message.get_placeholder_names(),
                'customer': customer,
                'customer_id': self.kwargs.get('customer_id') or customer.pk,
                'base_url': self.request.build_absolute_uri('/').rstrip('/'),
            }
        )

        return context


class UpdateSingleMessageView(UpdateMessageView):

    def _get_messages(self):
        return Message.objects.filter(pk=self.kwargs['message_id'])

    def _get_strings(self):
        return []

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)
        context['single_message'] = self._get_messages()[0]
        return context


class ListMessagesView(UpdateMessageView):

    template_name = 'message/list_messages.html'

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context.update({
        })

        return context


@login_required
def get_default_message(request, message_id):

    msg = get_object_or_404(DefaultMessage, pk=message_id, is_active=True)

    return HttpResponse(json.dumps({'content': msg.content}), content_type='text/json')


def get_message(request, message_id, secret_key):

    msg = get_object_or_404(Message, pk=message_id)
    if secret_key != msg.secret_key:
        capture_message('message key for {} is not {}'.format(message_id, secret_key))
        # raise Http404()  # TODO check python3 vs python2 hash change for key

    if not msg.active:
        msg = Message.objects.get_by_type(msg.type, customer=None)

    return HttpResponse(msg.content.rstrip('\n') + '\n', content_type='text/plain')
