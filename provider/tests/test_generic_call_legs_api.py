import re

from provider.tests.test_generic_call_api import GenericCallBaseTest, GenericCallPexipCachedMixin, \
    GenericCallPexipMixin


class GenericHangupTest(GenericCallBaseTest):

    @property
    def url(self):
        return '/json-api/v1/call_legs/{}/'.format(self.leg)

    def test_hangup(self):

        response = self.client.delete(self.url)
        self.assertContains(response, '', status_code=204)


class GenericPexipHangupTest(GenericCallPexipMixin, GenericHangupTest):
    pass


class GenericPexipCachedHangupTest(GenericCallPexipCachedMixin, GenericHangupTest):
    pass


class GenericGetTest(GenericCallBaseTest):

    @property
    def url(self):
        return '/json-api/v1/call_legs/?call={}'.format(self.call)

    @property
    def url_single(self):
        return '/json-api/v1/call_legs/{}/?call='.format(self.leg)

    def test_get(self):
        response = self.client.get(self.url)
        self.assertContains(response, '', status_code=200)

    def test_get_single(self):
        response = self.client.get(self.url_single)
        if self.customer.get_api().cluster.is_pexip:
            self.assertContains(response, self.space, status_code=200)
        else:
            self.assertContains(response, self.call, status_code=200)

    def test_tenant(self):
        provider = self.customer.get_api().cluster
        if not provider.is_pexip:
            return

        from datastore.models.pexip import Conference, Tenant
        Conference.objects.create(provider=provider,
                                  name=self.space,
                                  is_active=True,
                                  tenant=Tenant.objects.create(provider=provider, tid='999999999991234'))

        from statistics.models import Call, Leg
        Call.objects.all().update(tenant='999999999991234')
        Leg.objects.all().update(tenant='999999999991234')

        response = self.client.get(self.url_single)
        self.assertNotContains(response, self.space, status_code=404)

        response = self.client.get(self.url)
        self.assertNotContains(response, self.space, status_code=200)

        self.user.is_staff = True
        self.user.save()

        response = self.client.get(self.url_single)
        self.assertContains(response, self.space, status_code=200)

        self.customer.pexip_tenant_id = '1234'
        self.customer.save()


class GenericPexipGetTest(GenericCallPexipMixin, GenericGetTest):
    pass


class GenericPexipCachedGetTest(GenericCallPexipCachedMixin, GenericGetTest):
    pass


class GenericPexipCachedGetLookupTest(GenericCallPexipCachedMixin, GenericGetTest):

    @property
    def url(self):
        from statistics.models import Call
        call = Call.objects.first()
        return '/json-api/v1/call_legs/?call=lookup.{}'.format(call.id)

    @property
    def url_single(self):
        from statistics.models import Call
        call = Call.objects.first()
        return '/json-api/v1/call_legs/{}/?call=lookup.{}'.format(self.leg, call.id)


class GenericActionsTest(GenericCallBaseTest):
    def get_url(self, action):
        return '/json-api/v1/call_legs/{}/{}?call='.format(self.leg, action)

    def test_mute(self):
        response = self.client.post(self.get_url('set_mute/'), {'value': 1})
        self.assertContains(response, self.leg, status_code=200)

        response = self.client.post(self.get_url('set_mute/'), {'value': 0})
        self.assertContains(response, self.leg, status_code=200)

    def test_moderator(self):
        response = self.client.post(self.get_url('set_moderator/'), {'value': 1})
        self.assertContains(response, self.leg, status_code=200)

        response = self.client.post(self.get_url('set_moderator/'), {'value': 0})
        self.assertContains(response, self.leg, status_code=200)


class GenericPexipActionsTest(GenericCallPexipMixin, GenericActionsTest):
    pass


class GenericPexipCachedActionsTest(GenericCallPexipCachedMixin, GenericActionsTest):
    allow_status_call_api = True


class GenericCreateLegTest(GenericCallBaseTest):

    @property
    def url(self):
        return '/json-api/v1/call_legs/?call={}'.format(self.call)

    def test_post_call(self):
        data = {
            'call_id': self.call,
            'remote': 'test@mividas.com',
        }
        response = self.client.post(self.url, data)
        self.assertContains(response, '', status_code=200)

        self.allow_status_call_api = True  # live update needed after change

    def test_post_space(self):
        data = {
            'local': self.local_alias,
            'remote': self.remote_alias,
        }
        response = self.client.post(self.url, data)
        self.assertContains(response, '', status_code=200)

        self.allow_status_call_api = True  # live update needed after change


class GenericPexipCreateLegTest(GenericCallPexipMixin, GenericCreateLegTest):

    default_system_location = 'TESTLOC'

    def _init_system_location(self):
        c_settings = self.pexip.cluster.get_cluster_settings(self.customer)
        c_settings.dial_out_location = self.default_system_location
        c_settings.save()

    def test_post_call(self):

        self._init_system_location()
        super().test_post_call()
        self.assertSentAPIValueEquals(
            'command/v1/participant/dial/', 'system_location', self.default_system_location
        )

    def test_custom_system_location(self):

        self.user.is_staff = True
        self.user.save()

        data = {
            'call_id': self.call,
            'remote': 'test@mividas.com',
            'system_location': 'CUSTOM',
        }
        response = self.client.post(self.url, data)
        self.assertContains(response, '', status_code=200)

        self.assertSentAPIValueEquals(
            'command/v1/participant/dial/', 'system_location', data['system_location']
        )

        self.user.is_staff = False
        self.user.save()

        response = self.client.post(self.url, data)
        self.assertContains(response, '', status_code=200)

        self._init_system_location()
        self.assertSentAPIValueNotEquals(
            'command/v1/participant/dial/', 'system_location', data['system_location']
        )


class GenericPexipCachedCreateLegTest(GenericCallPexipCachedMixin, GenericCreateLegTest):
    pass


class GenericPexipCachedCreateLegLookupTest(GenericCallPexipCachedMixin, GenericCreateLegTest):

    @property
    def url(self):
        from statistics.models import Call
        call = Call.objects.first()
        return '/json-api/v1/call_legs/?call=lookup.{}'.format(call.id)
