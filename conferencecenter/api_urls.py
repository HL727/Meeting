from django.conf.urls import url
from django.contrib import staticfiles
from django.http import HttpResponse
from django.shortcuts import redirect
from django.templatetags.static import static
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.renderers import SwaggerUIRenderer
from drf_yasg.views import get_schema_view

from json_api.swagger import MividasScheduleSchemaGenerator
from meeting import api_views as views
from recording import api_views as recording
from shared.views import error_handler

api_urlpatterns = [
    url(r'^meeting/book/?$', views.Book.as_view()),
    url(r'^meeting/?$', views.Book.as_view(), name='api_book'),

    url(r'^meeting/message/(?P<meeting_id>\d+[_-][^/]+)/?$', views.MeetingMessage.as_view(), name='api_meeting_message'),
    url(r'^meeting/message/(?P<meeting_id>\d+[_-][^/]+)/moderator/$', views.ModeratorMessage.as_view(), name='api_meeting_moderator_message'),

    url(r'^meeting/webinar-moderator-message/(?P<meeting_id>\d+[_-][^/]+)/?$', views.ModeratorMessage.as_view(), name='api_meeting_webinar_moderator_message'),  # TODO remove url after portal has been upgrades

    url(r'^meeting/(?P<meeting_id>\d+[_-][^/]+)/?$', views.meeting_rest, name='api_meeting_rest'),
    url(r'^meeting/(?P<meeting_id>\d+[_-][^/]+)/confirm/?$', views.ConfirmMeetingView.as_view(), name='api_meeting_confirm'),

    url(r'^meeting/update/(?P<meeting_id>\d+[_-][^/]+)/?$', views.ReBook.as_view(), name='api_rebook'),
    url(r'^meeting/unbook/(?P<meeting_id>\d+[_-][^/]+)/?$', views.UnBook.as_view(), name='api_unbook'),

    url(r'^meeting/settings/(?P<meeting_id>\d+[_-][^/]+)/?$', views.UpdateSettings.as_view(), name='api_meeting_settings'),

    url(r'^status/?$', views.Status.as_view(), name='api_status'),
    url(r'^status/up/$', lambda request: HttpResponse('OK')),
]

# extended key permissions
extended_api_urlpatterns = [
    url(r'^user/cospaces/$', views.UserCospacesListView.as_view(), name='api_user_cospaces'),
    url(r'^user/status/$', views.UserStatus.as_view(), name='api_user_status'),
    url(r'^account_status/$', views.UserStatus.as_view()),  # deprecated
    url(r'^user/recordings/$', recording.UserRecordingsListView.as_view(), name='api_user_recordings'),
    url(r'^user/cospaces/(?P<cospace_id>[a-f0-9-]+)/invite/$', views.UserCospaceInviteMessage.as_view(), name='api_user_cospace_invite'),
    url(r'^user/invite/$', views.UserInviteMessage.as_view(), name='api_user_invite'),
    url(r'^recording/info/(?P<secret_key>.+)/$', recording.RecordingInfoView.as_view(), name='api_recording_info'),
    url(r"^recording/(?P<secret_key>.*)/$", recording.get_recording, name="api_get_recording"),
    url(
        r"^user/cospaces/(?P<cospace_id>[a-f0-9-]+)/$",
        views.ChangeUserCoSpaceSettings.as_view(),
        name="api_user_cospace_change",
    ),
    url(r"^addressbook/search/$", views.AddressBookSearch.as_view(), name="api_addressbook_search"),
]

deprecated_urlpatterns = [
    url(r'^strings/?$', views.WelcomeMessage.as_view(), name='api_welcome_message'),
    url(
        r'^quickchannel_callback/?$',
        recording.quickchannel_callback,
        name='api_quickchannel_callback',
    ),
]

# ldapadmin/end user admin cospace management api
cospace_urlpatterns = [
    url(r'^webinar/?$', views.Webinar.as_view(), name='api_webinar'),
    url(r'^webinar/list/?$', views.WebinarList.as_view(), name='api_webinar_list'),
    url(r'^cospace/?$', views.UpdateCoSpace.as_view(), name='api_cospace'),
    url(r'^cospace/list/?$', views.CoSpaceList.as_view(), name='api_cospace_list'),
    url(
        r'^cospace/(?P<cospace_id>\d+[_-][^/]+)/?$',
        views.UpdateCoSpace.as_view(),
        name='api_cospace',
    ),
    url(
        r'^cospace/(?P<cospace_id>\d+[_-][^/]+)/members/?$',
        views.CoSpaceMembers.as_view(),
        name='api_cospace_members',
    ),
    url(r'^sync_users/?$', views.SyncUsers.as_view(), name='api_sync_users'),
]

urlpatterns = [
    url(r'^api/v1/', include(api_urlpatterns)),
    url(r'^api/v1/', include(extended_api_urlpatterns)),
    url(r'^api/v1/', include(cospace_urlpatterns)),
    url(r'^api/v1/', include(deprecated_urlpatterns)),
    url(r'^$', views.book_start, name='book_start'),
    url(r'^status/$', views.celery_status, name='celery_status'),
    url(r'^status/up/$', lambda request: HttpResponse('OK')),
    url(r'^', include('emailbook.urls')),  # TODO split(?)
]

swagger_info = openapi.Info(
    title="Mividas Core Scheduling API",
    default_version='v1',
    description=(
        "API for Mividas Core. Use headers `X-Mividas-OU` containing `Customer` shared key, "
        "and `X-Mividas-Token` containing API Key for authentication. "
        "Up until v3.0.0-rc3, request body should be sent as `application/x-www-form-urlencoded` "
        "instead of `application/json` with nested objects as JSON-serialized strings"
    ),
)

schema_view = get_schema_view(
    swagger_info,
    generator_class=MividasScheduleSchemaGenerator,
    patterns=[
        # TODO finish f-meeting-api-drf
        # path('api/v1/', include(api_urlpatterns)),
        # path('api/v1/', include(extended_api_urlpatterns)),
    ],
    public=False,
)

SwaggerUIRenderer.template = 'swagger.html'


def hijack_spec(view):
    """
    TODO: finish f-meeting-api-drf and remove this
    """

    def inner(request, *args, **kwargs):
        if request.GET.get('format'):
            from django.contrib.staticfiles.storage import staticfiles_storage

            return redirect(staticfiles_storage.url('mividas-core-scheduling-api-schema.json'))
        return view(request, *args, **kwargs)

    return inner


urlpatterns += [
    path(
        'api/v1/',
        include(
            [
                url(
                    r'^swagger(?P<format>\.json|\.yaml)$',
                    hijack_spec(schema_view.without_ui(cache_timeout=0)),
                    name='schema-json',
                ),
                url(
                    r'^$',
                    hijack_spec(schema_view.with_ui('swagger', cache_timeout=60)),
                    name='schema-swagger-ui',
                ),
                url(r'^swagger/$', hijack_spec(schema_view.with_ui('swagger', cache_timeout=60))),
                url(
                    r'^redoc/$',
                    hijack_spec(schema_view.with_ui('redoc', cache_timeout=60)),
                    name='schema-redoc',
                ),
            ]
        ),
    )
]

handler500 = error_handler
