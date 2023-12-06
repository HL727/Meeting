from django.conf.urls import url

from shared.views import VueSPAView

urlpatterns = [
    url('policy/rules/', VueSPAView.as_view(), name='policy_rules'),
    url('policy/rules/add/', VueSPAView.as_view(), name='policy_rules_add'),
    url(r'policy/rules/(?P<id>\d+)/', VueSPAView.as_view(), name='policy_rules_edit'),
]
