
def init(decorate=None):

    if not decorate:
        decorate = lambda x: x

    from endpoint.ext_api.cisco_ce import CiscoCEProviderAPI
    from endpoint.ext_api.poly_group import PolyGroupProviderAPI
    from endpoint.ext_api.poly_hdx import PolyHDXProviderAPI
    from endpoint.ext_api.poly_studiox import PolyStudioXProviderAPI
    from endpoint.ext_api.poly_trio import PolyTrioProviderAPI

    from .cisco_ce import cisco_ce_post
    from .poly_group import poly_group_post
    from .poly_hdx import poly_hdx_post
    from .poly_trio import poly_trio_post
    from .poly_x import poly_x_post

    CiscoCEProviderAPI.override_post = decorate(cisco_ce_post)
    PolyGroupProviderAPI.override_post = decorate(poly_group_post)
    PolyStudioXProviderAPI.override_post = decorate(poly_x_post)
    PolyHDXProviderAPI.override_post = decorate(poly_hdx_post)
    PolyTrioProviderAPI.override_post = decorate(poly_trio_post)

