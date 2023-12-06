import os
import sys
os.environ['ALLOW_SENTRY'] = '0'

import django
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware


USERNAME = 'mividas_fallback'
CUSTOMER = 11
if len(sys.argv) > 1:
    URL = sys.argv[1]
    if '://' in URL:
        URL = '/' + URL.split('://', 1)[1].split('/', 1)[1]
else:
    URL = ''

import cProfile, pstats, io

pr = cProfile.Profile()

def start():
    pr.enable()

def stop():
    pr.disable()
    s = io.StringIO()
    sortby = 'cumtime' # SortKey.CUMULATIVE
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(100)
    print(s.getvalue())



def run():
    from django.contrib.auth.models import User

    from statistics.views import StatsView
    #templates['plotly']
    from django.urls import reverse
    reverse('stats_pdf')

    start()

    headers = {'HTTP_X_MIVIDAS_CUSTOMER': CUSTOMER}
    rf = RequestFactory()
    request = rf.get(URL + '&customer=' + str(CUSTOMER), headers=headers)

    middleware = SessionMiddleware()
    middleware.process_request(request)
    request.session.save()
    print(request.path, request.GET)

    request.user = User.objects.get(username=USERNAME)

    s = StatsView().as_view()
    try:
        s(request)
    except Exception as e:
        print(e)

    stop()






if __name__ == '__main__':
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'conferencecenter.settings')
    django.setup()
    run()
