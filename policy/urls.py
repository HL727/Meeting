from django.shortcuts import redirect
from django.urls import path, re_path

from debuglog.views import VueSPAView
from . import views

urlpatterns = [
    path('policy/report/', lambda request: redirect('policy_report')),
    path('policy/limits/', lambda request: redirect('policy_live')),
    path('analytics/policy/report/', views.PolicyReportView.as_view(), name='policy_report'),
    path('analytics/policy/', views.PolicyReportView.as_view(), name='policy_live'),
    path('policy/report/', views.PolicyReportView.as_view()),
    path('policy/limits/', views.PolicyReportView.as_view()),
    path('debug/policy/log/', VueSPAView.as_view(), name='policy_log'),
    path('cdr/policy/<secret_key>/policy/v1/service/configuration', views.policy_service_response),

    re_path('^admin/policy_auth/policywhitelist.*',
            lambda request: redirect(request.path.replace('policywhitelist', 'policyauthorizationoverride'))),

]
