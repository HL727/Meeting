from django.conf.urls import url
from . import views

urlpatterns = [
    url('email/book/', views.handle_http, name='emailbook_book'),
    url('email/unbook/(?P<secret_key>.+)/', views.unbook, name='emailbook_unbook'),
]
