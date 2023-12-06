from django.conf.urls import include, url
from exchange.views import EWSOauthSetup, EWSSetup, EWSOauthComplete, EWSOauthVerify

urlpatterns = [
    url(r'^setup/ews/$', EWSSetup.as_view(), name='onboard_ews'),
    url(r'^setup/ews/oauth/$', EWSOauthSetup.as_view(), name='onboard_ews_oauth'),
    url(r'^setup/ews/oauth/verify/$', EWSOauthVerify.as_view(), name='ews_oauth_verify'),
    url(r'^setup/ews/oauth/(?P<pk>\d+)/$', EWSOauthComplete.as_view(), name='onboard_ews_complete'),
]
