from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from provider.exceptions import NotFound, ResponseError
from customer.view_mixins import CustomerMixin
from .models import AcanoRecording


class RecordingView(CustomerMixin, TemplateView):

    template_name = 'recording/play.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        recording = get_object_or_404(AcanoRecording, secret_key=self.kwargs['secret_key'])
        context['recording'] = recording
        context['recordings'] = AcanoRecording.objects.filter(cospace_id=recording.cospace_id)
        try:
            context['cospace'] = self.customer.get_api().get_cospace(recording.cospace_id)
        except (ResponseError, NotFound):
            pass

        return context
