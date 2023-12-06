from django.urls import path

from rest_framework.routers import SimpleRouter

from policy import api_views

router = SimpleRouter()
router.register('customer_policy', api_views.CustomerPolicyViewSet)
router.register('customer_policy_state', api_views.CustomerPolicyStateViewSet)

router.register('debug/policy_log', api_views.PolicyLogViewSet)
router.register('debug/external_policy_log', api_views.ExternalPolicyLogViewSet)
router.register('debug/active_participant', api_views.ActiveParticipantViewSet)

urlpatterns = [
    path('policy/report/', api_views.PolicyReportView.as_view()),
    path('debug/leg/', api_views.LegDebugInfo.as_view()),
]

