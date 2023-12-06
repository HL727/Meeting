from rest_framework.routers import DefaultRouter
from . import api_views as views

router = DefaultRouter()
router.register('policy_rule', views.PolicyRuleViewSet)
