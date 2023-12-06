from django.conf import settings

mocker = None

if settings.TEST_MODE:
    import requests_mock

    mocker = requests_mock.Mocker()
    mocker.start()

