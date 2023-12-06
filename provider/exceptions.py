

class InvalidData(Exception):

    def __init__(self, title, fields: dict = None):

        self.fields = fields or {}
        super().__init__(self, title)


class InvalidKey(Exception):

    pass


class AuthenticationError(Exception):  # TODO: should this be a ResponseError?

    def get_message(self):
        if len(self.args) > 1 and hasattr(self.args[1], 'text'):
            return self.args[1].text or 'Authentication error'
        return 'Authentication error'


class ResponseError(Exception):

    def get_message(self):
        if len(self.args) > 1 and hasattr(self.args[1], 'text'):
            return self.args[1].text or str(self.args[0]) or 'Response error'
        return 'Response error'

    def get_all_errors(self):
        if self.args and len(self.args) > 2 and isinstance(self.args[2], dict):
            return self.args[2]

    @property
    def response(self):
        if len(self.args) > 1 and hasattr(self.args[1], 'text'):
            return self.args[1]
        return None


class MessageResponseError(ResponseError):
    def get_message(self):
        if self.args and isinstance(self.args[0], str):
            return self.args[0]
        return super().get_message()


class InvalidSSLError(ResponseError):
    pass


class DuplicateError(ResponseError):

    def get_message(self):
        if len(self.args) > 1 and hasattr(self.args[1], 'text'):
            # TODO get error
            return self.args[1].text
        return ''


class MultipleResponseError(ResponseError):

    def get_message(self):
        messages = {getattr(arg[1], 'text', '') for arg in self.args}
        if len(messages) > 1:
            return 'Multiple: {}'.format(', '.join(messages))

        return '{}'.format(', '.join(messages))

class NotFound(ResponseError):
    pass


class ResponseConnectionError(ResponseError):
    pass


class ProxyError(ResponseConnectionError):
    pass


class ResponseTimeoutError(ResponseConnectionError):
    pass
