from django.urls import path

from numberseries import views

urlpatterns = [
    path('numberseries/edit/', views.ProviderNumberSeriesView.as_view(), name='numberserie_edit'),
    path('numberseries/provider/<action>/', views.ProviderNumberSeriesAjax.as_view(), name='numberserie_provider_ajax'),
]