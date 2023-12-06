from django.conf.urls import url

from ui_message import views

urlpatterns = [
    url(r'^core/admin/messages/$', views.ListMessagesView.as_view(), {'current_customer': True}),
    url(r'^core/admin/messages/all/$', views.ListCustomers.as_view(), name='list_customers'),
    url(r'^core/admin/default_message/(?P<message_id>\d+)/$', views.get_default_message, name='get_default_message'),
    url(r'^core/admin/message/(?P<message_id>\d+)/(?P<secret_key>.+)/?$', views.get_message, name='get_message'),

    url(r'^core/admin/message/update/default/$', views.UpdateMessageView.as_view(), {'customer_id': 'default'}, name='update_messages'),
    url(r'^core/admin/message/update/(?P<customer_id>\d+|default)/$', views.UpdateMessageView.as_view(), name='update_messages'),

    url(r'^core/admin/messages/list/(?P<customer_id>\d+|default)/$', views.ListMessagesView.as_view(), name='list_messages'),

    url(r'^core/admin/messages/edit/(?P<customer_id>\d+|default)/$', views.UpdateMessageView.as_view(), name='update_messages'),

    url(r'^core/admin/messages/edit_single/(?P<customer_id>\d+|default)/(?P<message_id>\d+)/$', views.UpdateSingleMessageView.as_view(), name='update_single_message'),
]

