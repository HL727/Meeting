import sentry_sdk
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from django.views.decorators.csrf import csrf_exempt
from requests import Response
from rest_framework.decorators import api_view
from sentry_sdk import capture_exception, capture_message

from address.ext_api.tms import TMSSearch
from address.models import AddressBook


@csrf_exempt
def tms_soap(request, address_book_key=''):

    if request.method == "GET":
        return HttpResponse('Method GET not supported.', status=400)

    try:
        from debuglog.models import EndpointCiscoEvent
        EndpointCiscoEvent.objects.store(ip=request.META.get('REMOTE_ADDR'), content=request.body,
                                             event='search')
    except Exception:
        capture_exception()

    action = request.META.get('HTTP_SOAPACTION')
    if action == 'http://www.tandberg.net/2004/06/PhoneBookSearch/Search':
        address_book = get_object_or_404(AddressBook, secret_key=address_book_key)
        result = tms_search(address_book, request.body)
        return HttpResponse(result, content_type='text/xml')

    with sentry_sdk.push_scope() as scope:
        scope.set_extra('body', request.body)
        capture_message('SOAP Action {} not found'.format(action))

    return HttpResponse('Not found', status=404)


def tms_search(address_book, xml_body):

    return TMSSearch(xml_body).search(address_book)


@api_view
def json_search(request, address_book_key=''):

    from meeting.api_views import addressbook_json_search

    address_book = get_object_or_404(AddressBook, secret_key=address_book_key)

    return Response(addressbook_json_search(request, address_book))
