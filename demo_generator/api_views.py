from drf_yasg.utils import swagger_auto_schema
from datetime import date

from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import permissions

from rest_framework.viewsets import ViewSet

from .serializers import DemoGeneratorResponseSerializer, DemoGeneratorHeadCountSerializer, DemoGeneratorCallsSerializer
from .utils.call_statistics import DemoCallsGenerator
from .utils.head_count import DemoHeadCountGenerator


class DemoGeneratorViewSet(ViewSet):
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['POST'])
    @swagger_auto_schema(request_body=DemoGeneratorCallsSerializer, responses={200: DemoGeneratorResponseSerializer()})
    def call_statistics(self, request):
        serializer = DemoGeneratorCallsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        generator = DemoCallsGenerator(customer=data.get('customer'),
                                       server=data.get('server'),
                                       endpoint_server=data.get('endpoint_server'),
                                       endpoints=data.get('endpoints'),
                                       cospaces=data.get('cospaces'))

        response = generator.generate_call_statistics(start_date=date.today(),
                                                      days_back=data.get('days'),
                                                      number_of_calls=data.get('calls'),
                                                      participants=data.get('participants'),
                                                      endpoint_percent=data.get('endpoint_percent'),
                                                      random_cospace=data.get('randomize_meeting_room'))

        return Response(response)

    @action(detail=False, methods=['POST'])
    @swagger_auto_schema(request_body=DemoGeneratorHeadCountSerializer, responses={200: DemoGeneratorResponseSerializer()})
    def head_count(self, request):
        serializer = DemoGeneratorHeadCountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        generator = DemoHeadCountGenerator(customer=data.get('customer'),
                                           endpoints=data.get('endpoints'))

        response = generator.generate_head_count(start_date=date.today(),
                                                 days_back=data.get('days'))

        return Response(response)
