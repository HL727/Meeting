from typing import Union

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django.utils.translation import gettext as _

from license import license_quantity_left, AddonType


def license_validate_add(
    addon: AddonType, quantity=1, raise_exception=True
) -> Union[Response, None]:
    allowed = license_quantity_left(addon)
    if quantity <= allowed:
        return

    dct = {'status': 'error', 'error': _('Din licens tillåter inte den här åtgärden')}
    if raise_exception:
        raise ValidationError(dct)

    return Response(dct, status=400)
