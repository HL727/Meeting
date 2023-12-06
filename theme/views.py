from django.views.generic import TemplateView
from customer.view_mixins import LoginRequiredMixin, CustomerMixin


class VueSPAView(LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'base_vue.html'
