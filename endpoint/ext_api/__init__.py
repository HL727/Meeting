from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from .cisco_ce import CiscoCEProviderAPI
    from .poly_group import PolyGroupProviderAPI
    from .poly_hdx import PolyHDXProviderAPI
    from .poly_trio import PolyTrioProviderAPI

    AnyEndpointAPI = Union[
        CiscoCEProviderAPI, PolyGroupProviderAPI, PolyTrioProviderAPI, PolyHDXProviderAPI
    ]
else:
    AnyEndpointAPI = Any
