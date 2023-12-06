from django.http import Http404
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView

from .models import AdminOrganization, BackendAdministrator, PortalAdministrator, VideoCenterAdministrator

from customer.view_mixins import LoginRequiredMixin


class AdminIndex(LoginRequiredMixin, TemplateView):

    template_name = 'cospace/list.html'


class DisplayOrganization(LoginRequiredMixin, TemplateView):

    template_name = 'adminusers/display.html'
    model = AdminOrganization

    def dispatch(self, request, *args, **kwargs):

        obj = self.get_object()
        if not obj.users.filter(pk=self.request.user.pk) and not request.user.is_staff:
            raise Http404()

        return super().dispatch(
            request, *args, **kwargs)

    def get_object(self) -> AdminOrganization:
        return get_object_or_404(AdminOrganization, pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['organization'] = self.get_object()
        return context

    def post(self, request, *args, **kwargs):

        if request.POST.get('delete_backend'):
            BackendAdministrator.objects.filter(pk=request.POST.get('delete_backend'), organization=self.get_object()).update(delete_requested=True)
        if request.POST.get('delete_portal'):
            PortalAdministrator.objects.filter(pk=request.POST.get('delete_backend'), organization=self.get_object()).update(delete_requested=True)
        if request.POST.get('delete_videocenter'):
            VideoCenterAdministrator.objects.filter(pk=request.POST.get('delete_backend'), organization=self.get_object()).update(delete_requested=True)

        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password') or ''

        if request.POST.get('create_backend') and username and email:
            BackendAdministrator.objects.create(organization=self.get_object(), username=username, email=email, password=password, confirmed=False)

        if request.POST.get('create_portal') and username and email:
            PortalAdministrator.objects.create(organization=self.get_object(), username=username, email=email, password=password, confirmed=False)

        if request.POST.get('create_videocenter') and username and email:
            VideoCenterAdministrator.objects.create(organization=self.get_object(), username=username, email=email, password=password, confirmed=False)


        return redirect(self.get_object().get_absolute_url())

