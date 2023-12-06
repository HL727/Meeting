
def get_next_number(name, content_object=None, prefix=None, suffix=None, default=''):

    from .models import NumberSeriesManager
    return NumberSeriesManager.objects.get_next(name, content_object=None, prefix=None, suffix=None, default='')
