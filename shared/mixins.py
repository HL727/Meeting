from django.utils.decorators import method_decorator
from reversion.views import create_revision


class CreateRevisionViewSetMixin:

    @method_decorator(create_revision(atomic=False))
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @method_decorator(create_revision(atomic=False))
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @method_decorator(create_revision(atomic=False))
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
