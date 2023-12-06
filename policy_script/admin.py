from django.conf import settings
from django.contrib import admin

from policy_script.models import ClusterPolicyScript

# admin.site.register(MeetingPolicyScript)
if settings.ENABLE_CORE:
    admin.site.register(ClusterPolicyScript)
