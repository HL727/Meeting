from django.http import JsonResponse
from django.forms import ValidationError
from django.shortcuts import redirect
from django.utils.http import urlencode
from django.views.generic import ListView, DetailView, FormView
from drf_yasg.utils import swagger_auto_schema
from rest_framework.views import APIView

from meeting.serializers import MeetingSerializer, MeetingResponseSerializer, MeetingFilterSerializer
from meeting.models import Meeting
from supporthelpers.forms import MeetingFilterForm, CoSpaceForm
from supporthelpers.forms import MeetingForm
from supporthelpers.views.cospace import CospaceInviteView
from customer.view_mixins import LoginRequiredMixin, CustomerMixin


class MeetingList(CustomerMixin, LoginRequiredMixin, ListView):

    template_name = 'base_vue.html'

    def get_paginate_by(self, queryset):
        value = 50
        if self.request.GET.get('limit'):
            try:
                value = int(self.request.GET.get('limit'))
            except ValueError:
                pass

        return max(1, min(value, 1000))

    def dispatch(self, request, *args, **kwargs):
        super_result = super().dispatch(request, *args, **kwargs)
        if request.GET.get('reset_filter'):
            return redirect(request.path)
        return super_result

    def get(self, request, *args, **kwargs):
        if request.GET.get('ajax'):
            return self._ajax_results(request)
        return super().get(request, *args, **kwargs)

    def _ajax_results(self, request):
        context = self.get_context_data()
        if self.form.is_bound and not self.form.is_valid():
            return JsonResponse({
                'errors': self.form.errors,
            }, status=400)
        return JsonResponse({
            'results': MeetingSerializer(context['object_list'], many=True).data,
            'count': context['paginator'].count,
        })

    def get_queryset(self):
        args = dict(self.request.GET)
        args.pop('page', None)
        args.pop('customer', None)

        if args:
            self.form = MeetingFilterForm(self.request.GET, user=self.request.user, customer=self.customer)
        else:
            self.form = MeetingFilterForm(user=self.request.user, customer=self.customer)

        return self.form.get_meetings()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.form

        query = dict(list(self.request.GET.items()))
        query.pop('page', None)
        context['query'] = urlencode(query)

        return context


class MeetingListApiView(MeetingList, APIView):

    @swagger_auto_schema(query_serializer=MeetingFilterSerializer, responses={200: MeetingResponseSerializer})
    def get(self, request, *args, **kwargs):
        super().get(request)
        return self._ajax_results(request)


class BookMeetingView(CustomerMixin, LoginRequiredMixin, FormView):

    form_class = MeetingForm
    template_name = 'meeting/book.html'

    def form_valid(self, form):
        customer = self._get_customer()
        try:
            meeting = form.save(customer, self.request.META.get('REMOTE_ADDR'))
        except ValidationError:
            return self.form_invalid(form)
        return redirect('meeting_debug_details', meeting.pk)


class MeetingInviteView(CospaceInviteView):
    # TODO moderator invite

    def get_meeting(self, queryset=None):

        if self._has_all_customers():
            return Meeting.objects.get(pk=self.kwargs['meeting_id'])

        customer = self._get_customer(self.request)
        return Meeting.objects.get(customer=customer, pk=self.kwargs['meeting_id'])

    def _get_cospace(self):
        return CoSpaceForm(cospace=self.get_meeting().provider_ref2).load(customer=self._get_customer(self.request))

    def _get_invite_message(self, customer, cospace_id):
        from ui_message.models import Message

        if self.request.GET.get('message_type'):
            message_type = self._get_invite_message_type()
        else:
            message_type = None
        message = Message.objects.get_for_meeting(self.get_meeting(), message_type=message_type)
        meeting = self.get_meeting()

        content = message.format(meeting)

        return {
            'title': message.format_title(meeting),
            'content': content,
            'attachment': message.attachment,
            'plain': Message.objects.get_plain_message(content),
        }

    def get_context_data(self, **kwargs):
        return super().get_context_data(meeting=self.get_meeting())



class MeetingDebugDetails(CustomerMixin, LoginRequiredMixin, DetailView):

    template_name = 'supporthelpers/meeting_debug.html'
    context_object_name = 'meeting'

    def get_object(self, queryset=None) -> Meeting:

        if self._has_all_customers():
            return Meeting.objects.get(pk=self.kwargs['meeting_id'])

        customer = self._get_customer(self.request)
        return Meeting.objects.get(customer=customer, pk=self.kwargs['meeting_id'])

    def get_context_data(self, **kwargs):
        from recording.models import MeetingRecording
        from meeting.models import MeetingDialoutEndpoint
        from statistics.models import Call
        from recording.models import AcanoRecording

        context = super().get_context_data(**kwargs)

        meeting = self.get_object()

        try:
            cospace = meeting.api.get_cospace(meeting.provider_ref2)
        except Exception:
            pass
        else:
            context['cospace'] = cospace

        context['dialouts'] = MeetingDialoutEndpoint.objects.filter(meeting=meeting).order_by('ts_activated')
        context['recordings'] = MeetingRecording.objects.filter(meeting=meeting).order_by('ts_activated')
        context['endpoints'] = meeting.endpoints.filter(customer=meeting.customer)

        if meeting.provider_ref2:  # no external meetings
            context['calls'] = Call.objects.filter(cospace_id=meeting.provider_ref2)
            context['latest_calls'] = Call.objects.filter(cospace_id=meeting.provider_ref2).order_by('-ts_start')
            context['acano_recordings'] = AcanoRecording.objects.filter(cospace_id=meeting.provider_ref2)

        context['video_provider'] = meeting.customer.get_videocenter_provider()

        return context
