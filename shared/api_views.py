from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from shared.serializers import ExcelFileInputSerializer, ExcelCreateFileSerializer


class ExcelGetContent(APIView):

    def post(self, request):

        serializer = ExcelFileInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data)


class ExcelCreateFile(APIView):

    def post(self, request):

        serializer = ExcelCreateFileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return serializer.get_response()


class SetLanguage(APIView):

    def post(self, request):

        from django.utils import translation
        user_language = request.data.get('code')
        try:
            translation.activate(user_language)
        except ValueError:
            return Response({'code': 'Invalid code'}, status=400)

        request.session[getattr(translation, 'LANGUAGE_SESSION_KEY', '_translation')] = user_language

        response = Response({'status': 'OK'})
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, user_language)
        return response



