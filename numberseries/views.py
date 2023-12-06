from django.http import JsonResponse, Http404
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.views.generic.base import View

from numberseries.models import NumberSeries, NumberSeriesPrefix
from provider.models.provider import Provider
from customer.view_mixins import LoginRequiredMixin, CustomerMixin


class NumberSeriesView(TemplateView):

    template_name = 'numberseries/global.html'

    def get_series(self):

        return []


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['series'] = self.get_series()

        return context


class ProviderNumberSeriesView(LoginRequiredMixin, CustomerMixin, NumberSeriesView):

    def get_series(self):

        series = []

        for provider in Provider.objects.distinct():
            if not any([
                provider.is_acano,
            ]):
                continue

            cur_series = NumberSeries.objects.get_for('provider', provider)

            cur = [
                cur_series.get_prefix()
            ]

            for prefix in NumberSeriesPrefix.objects.filter(series=cur_series):
                if not (prefix.prefix == prefix.suffix == ''):
                    cur.append(prefix)

            series.append((provider, cur))
        return series

    def post(self, request, *args, **kwargs):

        for provider, series in self.get_series():

            for prefix in series:
                value = request.POST.get('provider-{}-{}'.format(provider.pk, prefix.pk))

                if value:
                    prefix.last_number = value
                    prefix.save()

        return redirect(request.path)


class ProviderNumberSeriesAjax(LoginRequiredMixin, CustomerMixin, View):

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):

        try:
            series = NumberSeries.objects.get(pk=request.GET.get('series_id'))
        except NumberSeries.DoesNotExist:
            raise Http404()

        # TODO check permission

        action = kwargs.get('action')

        if action == 'get_next':
            return JsonResponse({'number': series.get_next()})

        if request.method == "POST":
            if action == 'use_next':
                number = series.use_next()
                return JsonResponse({'number': number, 'next': series.get_next()})

        raise Http404()



