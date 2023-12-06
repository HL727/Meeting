from typing import Sequence, Optional

from django.conf import settings
from django.http import Http404

from customer.models import Customer

CUSTOMER_HEADERS = ['HTTP_X_MIVIDAS_CUSTOMER', 'HTTP_X_CUSTOMER']


def get_customers_from_request(request) -> Sequence[Customer]:
    if not request.user.is_authenticated:
        return Customer.objects.none()

    return Customer.objects.get_for_user(request.user)


def get_customer_from_request(request, customer_id=None) -> Optional[Customer]:

    if not request.user.is_authenticated:
        return None

    if getattr(request, 'mividas_customer', None):
        return request.mividas_customer

    def _update_request_customer(customer):
        request.mividas_customer = customer
        return customer

    customers = get_customers_from_request(request)

    kwarg_customer = getattr(request, 'resolver_match', None) and request.resolver_match.kwargs.get('customer_id')

    if not customer_id:
        if request.GET.get('customer'):
            customer_id = request.GET.get('customer')
        elif kwarg_customer:
            customer_id = request.resolver_match.kwargs['customer_id']
        elif any(request.META.get(header) for header in CUSTOMER_HEADERS):
            customer_id = [
                request.META[header] for header in CUSTOMER_HEADERS if request.META.get(header)
            ][0]
        elif len(customers) == 1:
            return _update_request_customer(customers[0])
        elif request.session.get('customer_id', ''):
            customer_id = str(request.session.get('customer_id', ''))
        else:
            customer_id = str(customers[0].pk) if customers else None  # set default customer

    if not customer_id:
        return _update_request_customer(None)

    for c in customers:
        if str(c.pk) == customer_id:
            if kwarg_customer and not request.GET.get('customer'):
                return c  # dont change customer for message views. use better solution for message views

            if '/json-api/' in request.path or '/api/' in request.path:  # dont replace customer for api views
                if request.session.get('customer_id'):
                    return _update_request_customer(c)

            set_customer(request, c)
            return _update_request_customer(c)

    if str(request.session.get('customer_id') or '') == str(customer_id):
        request.session.pop('customer_id', None)  # removed customer, reset session

    raise Http404


def user_has_all_customers(user):
    return Customer.objects.has_all_customers(user)

def set_customer(request, customer):
    request.session['customer_id'] = customer.pk

