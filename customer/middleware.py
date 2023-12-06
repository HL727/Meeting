from typing import Optional

from django.shortcuts import redirect

from customer.utils import get_customer_from_request


class CustomerMiddleware:
    """
    Check if customer is changed using request params.
    If so, redirect to list view instead of single object for the wrong customer
    """

    initial_customer_id: Optional[int]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self.initial_customer_id = request.session.get('customer_id')
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method != 'GET':
            return

        list_redirect = self.check_should_redirect_to_list(request, view_kwargs)
        if list_redirect:
            return list_redirect

    def check_should_redirect_to_list(self, request, view_kwargs):

        if '/json-api/v1/' in request.path or '/api/v1/' in request.path:
            return False

        if 'core/admin/message/' in request.path:  # some deprecated special customer_id=default code
            return False

        if not request.GET.get('check_customer'):
            return False

        customer = get_customer_from_request(request)
        if not self.initial_customer_id or not customer:
            return False

        if self.initial_customer_id == customer.pk:
            return False

        if view_kwargs.get('cospace_id'):
            return redirect('cospaces_list')
        elif view_kwargs.get('user_id'):
            return redirect('user_list')
        elif view_kwargs.get('call_id'):
            return redirect('calls')
        elif view_kwargs.get('endpoint_id'):
            return redirect('epm_list')
        elif view_kwargs.get('addressbook_id'):
            return redirect('addressbook_list')
