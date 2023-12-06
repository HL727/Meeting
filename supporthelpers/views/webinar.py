from django.views.generic.edit import FormView
from django.shortcuts import render, redirect, get_object_or_404
from ..forms import WebinarForm

from sentry_sdk import capture_exception

from django.conf import settings
from meeting.models import Meeting
from meeting.models import MeetingWebinar
from customer.view_mixins import LoginRequiredMixin, CustomerMixin


class WebinarView(LoginRequiredMixin, CustomerMixin, FormView):

    template_name = 'supporthelpers/webinar.html'

    form_class = WebinarForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        webinars = MeetingWebinar.objects.filter(meeting__backend_active=True)
        customer = self._get_customer()
        if customer:
            webinars = webinars.filter(meeting__customer=customer)
        context['webinars'] = webinars

        return context

    def post(self, request, *args, **kwargs):

        if request.POST.get('unbook'):
            meeting = get_object_or_404(Meeting, pk=int(request.POST['unbook']), customer=self._get_customer())

            from meeting.book_handler import BookingEndpoint
            BookingEndpoint({}, meeting.customer).unbook(meeting.pk)
            return redirect(request.path)

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):

        try:
            meeting, webinar = form.save(ip=self.request.META.get('REMOTE_ADDR'), creator=str(self.request.user), customer=self._get_customer())
        except Exception as e:
            if settings.DEBUG:
                raise
            capture_exception()
            data = {
                'error': e,
            }
            return render(self.request, 'supporthelpers/webinar.html', data)

        data = {
            'done': True,
            'meeting': meeting,
            'webinar': webinar,
        }

        return render(self.request, 'supporthelpers/webinar.html', self.get_context_data(**data))
