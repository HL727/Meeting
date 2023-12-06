from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.inspectors import (
    DjangoRestResponsePagination,
    SwaggerAutoSchema,
    ChoiceFieldInspector,
)
from drf_yasg.openapi import Parameter
from jsonfield import JSONField

from rest_framework import serializers
from rest_framework.pagination import LimitOffsetPagination

serializers.ModelSerializer.serializer_field_mapping[JSONField] = serializers.JSONField


def choicefield_process_result(self, result, method_name, obj, **kwargs):
    """Display choice info in description"""
    if isinstance(obj, serializers.ChoiceField):
        description = ''
        if result.get('description'):
            description = result.get('description', '').strip('.') + '.\n'

        choice_text = ',\n'.join('{}: {}'.format(*c) for c in obj.choices.items())
        result['description'] = '{}Choices:\n{}'.format(description, choice_text).lstrip(' .')
    return result


ChoiceFieldInspector.process_result = choicefield_process_result


class MividasScheduleSchemaGenerator(OpenAPISchemaGenerator):
    def get_security_definitions(self):
        return {
            'MividasToken': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'X-Mividas-Token',
            },
            'MividasOu': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'X-Mividas-OU',
            },
        }

    def get_security_requirements(self, security_definitions):
        return [
            {
                'MividasToken': [],
                'MividasOu': [],
            }
        ]


class MividasAutoSchema(SwaggerAutoSchema):

    def get_customer_parameters(self):
        customer_parameter = Parameter(
            'X-Mividas-Customer',
            'header',
            type='integer',
            required=False,
            description='Customer ID for current action (for use in multi-tenant installation)',
        )
        return [customer_parameter]

    def get_request_body_parameters(self, consumes):
        if '/api/v1/' not in self.path:
            return super().get_request_body_parameters(consumes) + self.get_customer_parameters()
        return super().get_request_body_parameters(consumes)


# monkey patch swagger
orig = DjangoRestResponsePagination.get_paginated_response


def new_get_paginated_response(self, paginator, response_schema):
    "monkey patched pagination response for dynamic pagination"

    if isinstance(paginator, LimitOffsetPagination) and not paginator.default_limit:
        return response_schema

    return orig(self, paginator, response_schema)


DjangoRestResponsePagination.get_paginated_response = new_get_paginated_response
