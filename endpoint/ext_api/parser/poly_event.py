from .tms_event import PassiveEndpointProvisionEvent


class PolyEvent(PassiveEndpointProvisionEvent):
    def __init__(
        self, endpoint_serial: str, customer=None, endpoint_mac=None, endpoint_secret=None
    ) -> None:

        self.serial = endpoint_serial
        self.mac = endpoint_mac
        super().__init__(customer=customer, endpoint_secret=endpoint_secret)

    def get_identification(self):

        return {
            'MACAddress': self.mac or '',
            'SerialNumber': self.serial,
            'IPAddress': '',
            'SystemName': '',
            'SWVersion': '',
        }
