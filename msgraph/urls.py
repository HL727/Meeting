from django.conf.urls import include, url
from .views import MSGraphOauthSetup, MSGraphOauthComplete, MSGraphOauthVerify

urlpatterns = [
    url(r'^setup/msgraph/$', MSGraphOauthSetup.as_view(), name='onboard_msgraph'),
    url(r'^setup/msgraph/oauth/verify/$', MSGraphOauthVerify.as_view(), name='msgraph_oauth_verify'),
    url(r'^setup/msgraph/oauth/(?P<pk>\d+)/$', MSGraphOauthComplete.as_view(), name='onboard_msgraph_complete'),
]
