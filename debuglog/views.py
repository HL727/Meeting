from django.views.generic import TemplateView
from customer.view_mixins import LoginRequiredMixin, CustomerMixin


class VueSPAView(LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'base_vue.html'
    title = ''

    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        if self.title:
            context.setdefault('title', self.title)
        return context
