from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from sentry_sdk import capture_exception

from endpoint.docs import BasicResponseSerializer
from organization.models import OrganizationUnit, CoSpaceUnitRelation
from organization.serializers import OrganizationUnitCreateSerializer
from provider.api.generic.mixins import DynamicAPIMixin
from provider.api.generic.serializers import GenericCoSpaceSerializer, BulkSetOrganizationUnitSerializer, \
    BulkSetTenantSerializer
from provider.exceptions import AuthenticationError, ResponseError
from provider.forms import CoSpaceForm
from customer.view_mixins import CustomerAPIMixin
from shared.utils import partial_update_or_create
from ui_message.models import Message


class GenericCoSpaceViewSet(DynamicAPIMixin, CustomerAPIMixin, viewsets.ViewSet):
    basename = 'cospace'
    serializer_class = GenericCoSpaceSerializer

    def _get_api(self, force_reload=False, allow_cached_values=True):
        return super()._get_api(force_reload=force_reload, allow_cached_values=allow_cached_values)

    def get_object(self, pk=None):
        cospace = CoSpaceForm(cospace=pk or self.kwargs['pk']).load(self._get_customer())

        if not cospace:
            raise NotFound()

        self._check_tenant_customer(cospace.get('tenant', ''))

        return self.transform(cospace, api=self._get_api())

    @staticmethod
    def transform_member(member, api, is_dynamic_provider=False):

        if api.provider.is_pexip:
            return member
        elif api.provider.is_acano:
            return member
        return member

    @staticmethod
    def transform(cospace, api, is_dynamic_provider=False):

        if api.provider.is_pexip:
            cospace = GenericCoSpaceViewSet.transform_from_pexip(cospace)

        if api.provider.is_acano:
            if 'organization_unit' not in cospace:
                cospace['organization_unit'] = CoSpaceUnitRelation.objects\
                    .filter(provider_ref=cospace['id']).values_list('unit', flat=True).first()

        return {
            **cospace,
            'sip_uri': api.get_sip_uri(cospace=cospace),
            'web_url': api.get_web_url(cospace=cospace),
        }

    @staticmethod
    def transform_from_pexip(conference):
        return {
            **conference,
            'title': conference.get('name') or conference.get('title') or '',
            'uri': conference.get('full_uri') or conference.get('uri') or '',
            'email': conference.get('primary_owner_email_address'),
        }

    # TODO serializer, swagger, org unit filter
    def list(self, request):

        q = request.GET.get('q') or request.GET.get('search') or ''
        try:
            offset = abs(int(request.GET.get('offset') or 0))
            limit = int(request.GET.get('limit') or 20)
        except ValueError:
            return Response({'error': 'Invalid integer'}, status=400)

        org_unit = None
        if request.GET.get('organization_unit'):
            try:
                org_unit = OrganizationUnit.objects.get(customer=self.customer,
                                                        pk=self.request.GET['organization_unit'])
            except OrganizationUnit.DoesNotExist:
                return Response({'organization_unit': 'Not found'}, status=400)

        provider, api, tenant_id = self._get_dynamic_provider_api(allow_cached_values=True)

        type = request.GET.get('type')
        if type == 'webinar' and provider.is_pexip:
            q_arg = {
                'name__icontains': q,
                'service_type': 'lecture'
            }
        elif type == 'cospace' and provider.is_pexip:
            q_arg = {
                'name__icontains': q,
                'service_type': 'conference'
            }
        else:
            q_arg = q

        api = self._get_api(allow_cached_values=True)

        if api.use_cached_values and q and not offset:  # cache first search page results
            try:
                self._get_api(allow_cached_values=False).find_cospaces(
                    q=q_arg,
                    tenant=tenant_id,
                    offset=0,
                    limit=20,
                )
            except (ResponseError, AuthenticationError):
                pass
            except Exception:
                capture_exception()

        result, count = api.find_cospaces(q=q_arg, tenant=tenant_id, org_unit=org_unit, offset=offset, limit=None if limit < 0 else limit)

        is_dynamic = self._check_dynamic_provider_api()

        return Response({
            'results': [self.transform(c, api=api, is_dynamic_provider=is_dynamic) for c in result],
            'count': count,
            'q': q,
            'page_from': offset + 1,
            'page_to': offset + len(result),
            'cached': getattr(api, 'use_cached_values', False),
        })

    def delete(self, request, pk=None):

        if request.GET.get('cospaces'):
            pks = [c.strip() for lst in request.GET.getlist('cospaces') for c in lst.split(',') if c.strip()]
        elif pk:
            pks = [pk]
        else:
            return Response({'cospaces': 'Must be provided'}, status=400)

        failed = False
        for pk in pks:
            try:
                obj = self.get_object(pk)  # check tenant
            except NotFound:
                continue

            if not self._get_api().delete_cospace(obj['id']):
                failed = True

        return Response(status=400 if failed else 204)

    # TODO serializer, swagger
    def retrieve(self, request, pk=None):
        obj = self.get_object()

        api = self._get_api(allow_cached_values=True)
        obj['members'] = [
            self.transform_member(member, api=api) for member in api.get_members(obj['id'])
        ]
        return Response(obj)

    @action(detail=True, methods=['GET'])
    def invite(self, request, pk=None):

        self.get_object()
        customer = self._get_customer()

        message = Message.objects.get_for_cospace(customer, pk, message_type='acano_cospace')

        return Response(message)

    @invite.mapping.post
    def send_invite(self, request, pk=None):

        obj = self.get_object()
        customer = self._get_customer()
        meeting = CoSpaceForm(cospace=obj['id']).get_temp_meeting(customer)

        if not meeting.creator_email:
            return Response({
                'error': 'No owner/email is specified for room',
            }, status=400)

        try:
            from ui_message.invite import send_email_for_cospace
            send_email_for_cospace(self._get_api(), obj['id'])
        except ValueError:
            return Response({
                'error': 'Message is empty',
            }, status=400)
        except Exception as e:
            return Response({
                'error': 'SMTP error: {}'.format(e),
            }, status=400)

        return Response({
            'status': 'OK',
            'email': meeting.creator_email,
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
            from provider.models.pexip import PexipSpace
            from datastore.models.pexip import Conference
            partial_update_or_create(PexipSpace, cluster=api.cluster, external_id=obj['id'],
                                     defaults=dict(organization_unit=org_unit))
            Conference.objects.filter(provider=api.cluster, cid=obj['id']).update(organization_unit=org_unit)
        elif api.provider.is_acano:
            from datastore.models.acano import CoSpace
            if org_unit:
                partial_update_or_create(CoSpaceUnitRelation, provider_ref=obj['id'],
                                         unit__customer=api.customer, defaults={'unit': org_unit})
            else:
                CoSpaceUnitRelation.objects.filter(provider_ref=obj['id'], unit__customer=api.customer).delete()
            CoSpace.objects.filter(provider=api.cluster, cid=obj['id']).update(organization_unit=org_unit)

        return Response({'status': 'OK'})

    @swagger_auto_schema(request_body=BulkSetOrganizationUnitSerializer(), responses={200: BasicResponseSerializer})
    @action(detail=False, methods=['PATCH'], url_path='set-organization-unit')
    def set_organization_unit_bulk(self, request):
        serializer = BulkSetOrganizationUnitSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        org_unit = serializer.get_organization()

        api = self._get_api(allow_cached_values=True)

        from provider.models.pexip import PexipSpace
        from datastore.models.pexip import Conference
        from datastore.models.acano import CoSpace

        for pk in serializer.validated_data['ids']:
            obj = self.get_object(pk=pk)
            if api.provider.is_pexip:
                partial_update_or_create(PexipSpace, cluster=api.cluster, external_id=obj['id'],
                                         defaults=dict(organization_unit=org_unit))
                Conference.objects.filter(provider=api.cluster, cid=obj['id']).update(
                    organization_unit=org_unit)
            elif api.provider.is_acano:
                if org_unit:
                    partial_update_or_create(CoSpaceUnitRelation, provider_ref=obj['id'],
                                             unit__customer=api.customer, defaults={'unit': org_unit})
                else:
                    CoSpaceUnitRelation.objects.filter(provider_ref=obj['id'], unit__customer=api.customer).delete()
                CoSpace.objects.filter(provider=api.cluster, cid=obj['id']).update(organization_unit=org_unit)

        return Response({'status': 'OK'})

    @swagger_auto_schema(request_body=BulkSetTenantSerializer(), responses={200: BasicResponseSerializer})
    @action(detail=False, methods=['PATCH'], url_path='set-tenant')
    def set_tenant_bulk(self, request):
        serializer = BulkSetTenantSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        tenant = serializer.validated_data['tenant']

        api = self._get_api(allow_cached_values=True)
        self._check_tenant_customer(tenant)

        for pk in serializer.validated_data['ids']:
            self.get_object(pk=pk)
            api.update_cospace(pk, {'tenant': tenant})

        return Response({'status': 'OK'})
