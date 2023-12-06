from typing import Iterable

from drf_yasg.utils import swagger_auto_schema, no_body
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from address.docs import ProvidersResponseSerializer, ErrorSerializer, AddressBookIdSerializer, \
    CopySerializer, SourceIdSerializer
from address.models import AddressBook, Item, ManualSource, Group, ManualLinkSource
from address.serializers import AddressBookSerializer, AddressBookListSerializer, ItemSerializer, \
    GroupEditSerializer, \
    SourceSerializer, ItemBulkSerializer, CreateSourceSerializer
from endpoint.view_mixins import CustomerRelationMixin


class AddressBookViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    serializer_class = AddressBookSerializer
    queryset = AddressBook.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return AddressBookListSerializer
        return self.serializer_class

    @action(detail=False)
    @swagger_auto_schema(responses={200: ProvidersResponseSerializer})
    def providers(self, request):

        from provider.models.vcs import VCSEProvider

        provider = self._get_customer().get_provider()
        cmses = [provider] if provider and provider.is_acano else []
        vcses = VCSEProvider.objects.filter_for_customer(self._get_customer())
        manuals = ManualSource.objects.filter(
            address_book__customer=self._get_customer(), groups__item__isnull=False
        )

        return Response({
            'cms': [{'id': cms.pk, 'title': str(cms)} for cms in cmses if cms],
            'vcs': [{'id': vcs.pk, 'title': str(vcs)} for vcs in vcses if vcs],
            'manual': [{'id': manual.pk, 'title': '{} ({})'.format(manual.title, manual.address_book).replace(' ()', '')} for manual in manuals],
        })

    @action(detail=True, methods=['POST'])
    @swagger_auto_schema(request_body=CreateSourceSerializer, responses={200: AddressBookSerializer, 400: ErrorSerializer})
    def source(self, request, pk=None):

        from . import models as m
        from django.forms import modelform_factory

        serializer = CreateSourceSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        input_data = request.data.copy()
        type = input_data['type']
        obj = self.get_object()

        exclude = {'exclude': ['address_book', 'type']}

        if type == 'epm':
            form_class = modelform_factory(m.EPMSource, **exclude)
        elif type == 'cms_user':
            form_class = modelform_factory(m.CMSUserSource, **exclude)
        elif type == 'cms_spaces':
            form_class = modelform_factory(m.CMSCoSpaceSource, **exclude)
        elif type == 'vcs':
            form_class = modelform_factory(m.VCSSource, **exclude)
        elif type == 'tms':
            form_class = modelform_factory(m.TMSSource, **exclude)
        elif type == 'seevia':
            form_class = modelform_factory(m.SeeviaSource, **exclude)
        elif type == 'manual_link':
            form_class = modelform_factory(m.ManualLinkSource, **exclude)
        else:
            return Response(data='Invalid type', status=400)

        form = form_class(input_data)
        if form.is_valid():
            source = form.save(commit=False)
            source.address_book = obj
            source.save()
        else:
            return Response({'status': 'error', 'errors': form.errors}, status=400)

        from endpoint import tasks
        tasks.sync_address_books.delay(pk=obj.pk)

        return Response({**self.get_serializer(obj).data, 'source_id': source.pk})

    @action(detail=True, methods=['POST', 'DELETE'])
    @swagger_auto_schema(request_body=SourceIdSerializer, responses={200: AddressBookSerializer})
    def remove_source(self, request, pk=None):

        from . import models as m
        obj = self.get_object()

        serializer = SourceIdSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        source = m.Source.objects.get(address_book=obj, pk=request.data['id'])

        links = m.ManualLinkSource.objects.filter(manual_source=request.data['id'])
        if links:  # replace linked source with the one to be removed (i.e. move it)
            link = links[0]
            source.address_book = link.address_book
            source.save()
            link.delete()
        else:
            source.delete()

        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['POST'])
    @swagger_auto_schema(request_body=SourceIdSerializer, responses={200: AddressBookSerializer})
    def make_source_editable(self, request, pk=None):

        from . import models as m
        obj = self.get_object()

        serializer = SourceIdSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        source = m.Source.objects.get(address_book=obj, pk=request.data['id'])
        source.merge_into_manual()

        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['POST'])
    @swagger_auto_schema(request_body=SourceIdSerializer, responses={200: SourceSerializer(many=True)})
    def check_source_links(self, request, pk=None):

        serializer = SourceIdSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        return self._get_source_links([serializer.validated_data['id']])

    @action(detail=True, methods=['GET'])
    @swagger_auto_schema(responses={200: SourceSerializer(many=True)})
    def source_links(self, request, pk=None):
        return self._get_source_links(ManualSource.objects.filter(address_book=self.get_object()))

    def _get_source_links(self, manual_sources: Iterable[ManualSource]):
        sources = ManualLinkSource.objects.filter(manual_source__in=manual_sources)
        return Response(SourceSerializer(sources, many=True).data)

    @action(detail=True, methods=['POST'])
    @swagger_auto_schema(request_body=CopySerializer)
    def copy(self, request, pk=None):

        serializer = CopySerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        new_book = self.get_object().copy(serializer.validated_data.get('new_title') or None,
                                          link_manual=not bool(serializer.validated_data.get('copy_editable_items')))
        from endpoint import tasks
        tasks.sync_address_books.delay(pk=new_book.pk)
        return Response(self.get_serializer(new_book).data)

    def get_serializer_context(self):

        if (self.lookup_url_kwarg or self.lookup_field) not in self.kwargs:
            return super().get_serializer_context()

        # only load for detail views
        manual_groups = (
            self.get_object().groups.filter(source__type='Manual').values_list('pk', flat=True)
        )

        return {
            **super().get_serializer_context(),
            'manual_groups': manual_groups,
        }

    @action(detail=True)
    @swagger_auto_schema(responses={200: ItemSerializer(many=True)})
    def items(self, request, pk=None):
        queryset = Item.objects.filter(group__address_book=self.get_object())

        serializer = ItemSerializer(
            queryset,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @action(detail=True)
    def export(self, request, pk=None):
        book = self.get_object()
        return book.export()

    @action(detail=True)
    def search(self, request, pk=None):
        book = self.get_object()

        from meeting.api_views import addressbook_json_search

        return Response(addressbook_json_search(request, book))

    @swagger_auto_schema(request_body=no_body)
    @action(detail=True, methods=['POST'])
    def sync(self, request, pk=None):
        book = self.get_object()
        book.sync()
        return Response(
            {
                'status': 'OK',
                'errors': [
                    {'source': source.pk, 'error': source.sync_errors}
                    for source in book.sources.all()
                    if source.sync_errors
                ],
            }
        )

    @action(detail=True)
    @swagger_auto_schema(responses={200: ItemSerializer(many=True)})
    def editable_items(self, request, pk=None):
        queryset = Item.objects.filter(group__address_book=self.get_object())

        serializer = ItemSerializer(
            queryset,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)


class GroupViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    serializer_class = GroupEditSerializer
    queryset = Group.objects.all().select_related('source')


class ItemViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    serializer_class = ItemSerializer
    queryset = Item.objects.all()

    def get_queryset(self):
        return super().get_queryset().prefetch_related('group', 'group__source', 'group__parent')

    @action(detail=False, methods=['POST'])
    def bulk_create(self, request):

        serializer = ItemBulkSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        serializer.save(customer=self._get_customer())

        return Response(serializer.data, status=201)


