import logging
import sys

from django.http import HttpResponseServerError, JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView
from sentry_sdk import capture_exception

from provider.exceptions import AuthenticationError, NotFound, ResponseError
from customer.view_mixins import CustomerMixin


logger = logging.getLogger(__name__)


class VueSPAView(CustomerMixin, TemplateView):

    template_name = 'base_vue.html'
    title = None

    def __init__(self, *args, **kwargs):
        self.title = kwargs.pop('title', None)
        super().__init__(*args, **kwargs)

    def get_context_data(self, **kwargs):
        return super().get_context_data(title=self.title)


def error_handler(request):

    title = message = ''

    try:
        exctype, value = sys.exc_info()[:2]
        if isinstance(value, AuthenticationError) or issubclass(exctype, AuthenticationError):
            title = 'Authentication Error'
        elif isinstance(value, NotFound) or issubclass(exctype, NotFound):
            title = 'External system could not find the requested object'
        elif isinstance(value, ResponseError) or issubclass(exctype, ResponseError):
            title = 'External system responded with an invalid response'
        else:
            title = 'Unknown error: {}'.format(exctype.__name__)
    except Exception:
        capture_exception()

    try:
        if request.path.startswith('/api/') or request.path.startswith('/json-api/'):
            return JsonResponse(
                {"status": "ERROR", "message": title or "Unhandled server error"}, status=500
            )
    except Exception:
        pass

    logger.warning('Unhandled error, %s', title, exc_info=True)

    try:
        return render(request, '500.html', {
            'title': title,
            'message': message,
        }, status=500)
    except Exception:
        pass

    try:
        sys.stderr.write('Unknown error:')
        sys.stderr.write(title)
        sys.stderr.write('\n')
    except (IOError, UnicodeEncodeError):
        sys.stderr.write('Couldnt write title\n')

    return HttpResponseServerError('An unknown error has occurred during render of 500 template: {}'.format(title))
