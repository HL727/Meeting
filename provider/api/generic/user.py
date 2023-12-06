from typing import Sequence

from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from sentry_sdk import capture_exception

from endpoint.docs import BasicResponseSerializer
from organization.models import OrganizationUnit, UserUnitRelation
from organization.serializers import OrganizationUnitCreateSerializer
from provider.api.generic.mixins import DynamicAPIMixin
from provider.api.generic.serializers import GenericUserSerializer, BulkSetOrganizationUnitSerializer
from customer.view_mixins import CustomerAPIMixin
from provider.exceptions import ResponseError, AuthenticationError
from shared.utils import partial_update_or_create
from ui_message.models import Message


class GenericUserViewSet(DynamicAPIMixin, CustomerAPIMixin, viewsets.ViewSet):
    basename = 'cospace'
    serializer_class = GenericUserSerializer

    def _get_api(self, force_reload=False, allow_cached_values=True):
        return super()._get_api(force_reload=force_reload, allow_cached_values=allow_cached_values)

    def get_object(self, pk=None):
        user = self._get_api().get_user(pk or self.kwargs['pk'])

        if not user:
            raise NotFound()

        self._check_tenant_customer(user.get('tenant', ''))

        return self.transform(user, is_dynamic_provider=self._check_dynamic_provider_api())

    def transform(self, user, is_dynamic_provider=False):

        if self._get_api().provider.is_pexip:
            return self.transform_from_pexip(user)
        return user

    @staticmethod
    def transform_from_pexip(user):
        name = user.get('name') or user.get('display_name')
        if not name:
            name = '{} {}'.format(user['first_name'], user['last_name']).strip() or user['primary_email_address']

        return {
            **user,
            'name': name,
            'email': user.get('email') or user.get('primary_email_address'),
        }

    def list(self, request):

        q = request.GET.get('q') or request.GET.get('search') or ''
        try:
            offset = int(request.GET.get('offset') or 0)
            limit = int(request.GET.get('limit') or 20)
        except ValueError:
            return Response({'error': 'Invalid integer'}, status=400)

        tenant_id = self._get_tenant_id()
        if self.request.GET.get('all') and self._has_all_customers():
            tenant_id = None

        org_unit = None
        if request.GET.get('organization_unit'):
            try:
                org_unit = OrganizationUnit.objects.get(customer=self.customer,
                                                        pk=self.request.GET['organization_unit'])
            except OrganizationUnit.DoesNotExist:
                return Response({'organization_unit': 'Not found'}, status=400)

        api = self._get_api()

        if api.use_cached_values and q and not offset:  # cache first search page results
            try:
                self._get_api(allow_cached_values=False).find_users(
                    q=q,
                    tenant=tenant_id,
                    offset=0,
                    limit=20,
                )
            except (ResponseError, AuthenticationError):
                pass
            except Exception:
                capture_exception()

        result, count = api.find_users(q=q, tenant=tenant_id, org_unit=org_unit, offset=offset,
                                       limit=None if limit < 0 else limit, include_user_data=True)

        if offset in (0, None):  # try add ldap user match
            ldap_user = self.get_ldap_match_user(api, q, tenant_id=tenant_id)
            if ldap_user:
                result.insert(0, ldap_user)
                count += 1

        is_dynamic_provider = self._check_dynamic_provider_api()
        result = [self.transform(u, is_dynamic_provider=is_dynamic_provider) for u in result]

        return Response({
            'results': result,
            'count': count,
            'q': q,
            'page_from': offset + 1,
            'page_to': offset + len(result),
            'cached': getattr(api, 'use_cached_values', False),
        })

    def get_ldap_match_user(self, api, q: str, tenant_id=None):
        # TODO pexip
        from datastore.models import acano  #, pexip

        tenant_query = {}
        if tenant_id is not None:
            tenant_query['tenant__tid'] = tenant_id

        try:
            username = acano.User.objects.filter(ldap_username=q or '-', **tenant_query).order_by('-last_synced')[0].username
            return api.find_users(q=username, tenant=tenant_id)[0][0]
        except IndexError:
            return None

    def retrieve(self, request, pk=None):
        obj = self.get_object()
        obj['cospaces'] = self._get_api().get_user_cospaces(obj['id'])
        return Response(obj)

    @action(detail=True, methods=['GET'])
    def invite(self, request, pk=None):

        obj = self.get_object()
        customer = self._get_customer()

        cospace = self._get_api().get_user_private_cospace(obj['id'])
        if not cospace:
            return Response({'error': 'User has not private cospace'}, status=404)

        message = Message.objects.get_for_cospace(customer, cospace['id'], message_type='acano_user')

        return Response(message)

    @invite.mapping.post
    @swagger_auto_schema(responses={200: BasicResponseSerializer})
    def send_invite(self, request, pk=None):

        obj = self.get_object()

        if not obj.get('email'):
            return Response({
                'error': 'No owner/email is specified for room',
            }, status=400)

        error = False
        try:
            from ui_message.invite import send_email_for_user_cospace
            if not send_email_for_user_cospace(self._get_api(), obj['id']):
                error = 'Unknown error'
        except Exception as e:
            error = e

        if error:
            return Response({
                'status': 'Error',
                'error': str(error),
            }, status=400)

        return Response({
            'status': 'OK',
            'email': obj['email'],
        })

    @swagger_auto_schema(request_body=OrganizationUnitCreateSerializer(), responses={200: BasicResponseSerializer})
    @action(detail=True, methods=['PATCH'], url_path='set-organization-unit')
    def set_organization_unit(self, request, pk=None):
        serializer = OrganizationUnitCreateSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        org_unit = serializer.get_organization()

        api = self._get_api(allow_cached_values=True)

        obj = self.get_object()

        if api.provider.is_pexip:
            from provider.models.pexip import PexipEndUser
            from datastore.models.pexip import EndUser
            partial_update_or_create(PexipEndUser, cluster=api.cluster, external_id=obj['id'],
                                     defaults=dict(organization_unit=org_unit))
            EndUser.objects.filter(provider=api.cluster, uid=obj['id']).update(organization_unit=org_unit)
        elif api.provider.is_acano:
            from datastore.models.acano import User
            if org_unit:
                partial_update_or_create(UserUnitRelation, user_jid=obj['jid'],
                                         unit__customer=api.customer, defaults={'unit': org_unit})
            else:
                UserUnitRelation.objects.filter(user_jid=obj['jid'], unit__customer=api.customer).delete()
            User.objects.filter(provider=api.cluster, uid=obj['id']).update(organization_unit=org_unit)

        return Response({'status': 'OK'})

    @swagger_auto_schema(request_body=BulkSetOrganizationUnitSerializer(), responses={200: BasicResponseSerializer})
    @action(detail=False, methods=['PATCH'], url_path='set-organization-unit')
    def set_organization_unit_bulk(self, request):
        serializer = BulkSetOrganizationUnitSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        org_unit = serializer.get_organization()

        api = self._get_api(allow_cached_values=True)

        from provider.models.pexip import PexipEndUser
        from datastore.models.pexip import EndUser
        from datastore.models.acano import User

        for pk in serializer.validated_data['ids']:
            obj = self.get_object(pk=pk)
            if api.provider.is_pexip:
                partial_update_or_create(PexipEndUser, cluster=api.cluster, external_id=obj['id'],
                                         defaults=dict(organization_unit=org_unit))
                EndUser.objects.filter(provider=api.cluster, uid=obj['id']).update(organization_unit=org_unit)
            elif api.provider.is_acano:
                if org_unit:
                    partial_update_or_create(UserUnitRelation, user_jid=obj['jid'],
                                             unit__customer=api.customer, defaults={'unit': org_unit})
                else:
                    UserUnitRelation.objects.filter(user_jid=obj['jid'], unit__customer=api.customer).delete()
                User.objects.filter(provider=api.cluster, uid=obj['id']).update(organization_unit=org_unit)

        return Response({'status': 'OK'})
