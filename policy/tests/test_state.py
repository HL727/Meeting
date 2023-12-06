from django.db import IntegrityError
import json
import sys
from io import StringIO

from customer.models import Customer
from policy.models import CustomerPolicyState, ActiveCall, ActiveParticipant
from .base import PolicyTestMixin


class StateTestCase(PolicyTestMixin):
    def setUp(self):
        super().setUp()
        self.customer_policy_state.active_participants = 0
        self.customer_policy_state.active_participants_gateway = 0
        self.customer_policy_state.active_calls = 0
        self.customer_policy_state.save()

    def _get_state(self):
        return {tuple(x) for x in CustomerPolicyState.objects.values_list('customer', 'active_calls', 'active_participants', 'active_participants_gateway')}

    def test_negative_participant(self):

        CustomerPolicyState.objects.change_participants(-1, customer=self.customer, cluster=self.cluster, guid='test', gateway=True)
        CustomerPolicyState.objects.change_participants(-1, customer=self.customer, cluster=self.cluster, guid='test', gateway=True)
        CustomerPolicyState.objects.change_participants(-1, customer=self.customer, cluster=self.cluster, guid='test', gateway=False)

        self.assertEqual(self._get_state(), {(self.customer.pk, 0, 0, 0)})

    def test_negative_call(self):

        CustomerPolicyState.objects.change_calls(-1, customer=self.customer, cluster=self.cluster, name='test')
        self.assertEqual(self._get_state(), {(self.customer.pk, 0, 0, 0)})
        CustomerPolicyState.objects.change_calls(1, customer=self.customer, cluster=self.cluster, name='test')
        self.assertEqual(self._get_state(), {(self.customer.pk, 1, 0, 0)})
        CustomerPolicyState.objects.change_calls(-1, customer=self.customer, cluster=self.cluster, name='test')
        self.assertEqual(self._get_state(), {(self.customer.pk, 0, 0, 0)})
        CustomerPolicyState.objects.change_calls(-1, customer=self.customer, cluster=self.cluster, name='test')
        CustomerPolicyState.objects.change_calls(-1, customer=self.customer, cluster=self.cluster, name='test2')

        self.assertEqual(self._get_state(), {(self.customer.pk, 0, 0, 0)})

    def test_positive_call(self):

        CustomerPolicyState.objects.change_calls(1, customer=self.customer, cluster=self.cluster, name='test')
        CustomerPolicyState.objects.change_calls(1, customer=self.customer, cluster=self.cluster, name='test')
        CustomerPolicyState.objects.change_calls(1, customer=self.customer, cluster=self.cluster, name='test2')
        self.assertEqual(self._get_state(), {(self.customer.pk, 2, 0, 0)})
        CustomerPolicyState.objects.change_calls(-1, customer=self.customer, cluster=self.cluster, name='test')

        self.assertEqual(self._get_state(), {(self.customer.pk, 1, 0, 0)})

    def test_positive_participant(self):

        CustomerPolicyState.objects.change_participants(1, customer=self.customer, cluster=self.cluster, guid='test', gateway=True)
        CustomerPolicyState.objects.change_participants(1, customer=self.customer, cluster=self.cluster, guid='test2', gateway=False)

        self.assertEqual(self._get_state(), {(self.customer.pk, 0, 2, 1)})

    def test_wrong_participant(self):

        customer2 = Customer.objects.create(title='test')

        CustomerPolicyState.objects.change_participants(1, customer=self.customer, cluster=self.cluster, guid='test', gateway=True)
        self.assertEqual(self._get_state(), {(self.customer.pk, 0, 1, 1),})

        CustomerPolicyState.objects.change_participants(1, customer=self.customer, cluster=self.cluster, guid='test', gateway=False)
        self.assertEqual(self._get_state(), {(self.customer.pk, 0, 1, 0),})

        CustomerPolicyState.objects.change_participants(1, customer=customer2, cluster=self.cluster, guid='test', gateway=False)
        self.assertEqual(self._get_state(), {(self.customer.pk, 0, 0, 0), (customer2.pk, 0, 1, 0), })

    def test_fallback(self):

        CustomerPolicyState.objects.change_participants(1, customer=self.customer, cluster=self.cluster, guid='test', gateway=True, fallback=True)
        self.assertEqual(self._get_state(), {(self.customer.pk, 0, 1, 1)})
        CustomerPolicyState.objects.change_participants(1, customer=self.customer, cluster=self.cluster, guid='test', gateway=False, fallback=True)
        self.assertEqual(self._get_state(), {(self.customer.pk, 0, 1, 1)})
        CustomerPolicyState.objects.change_participants(1, customer=self.customer, cluster=self.cluster, guid='test', gateway=True, fallback=True)

        self.assertEqual(self._get_state(), {(self.customer.pk, 0, 1, 1)})

        CustomerPolicyState.objects.change_participants(-1, customer=self.customer, cluster=self.cluster, guid='test', gateway=False, fallback=True)
        self.assertEqual(self._get_state(), {(self.customer.pk, 0, 0, 0)})  # remove gateway anyway
        CustomerPolicyState.objects.change_participants(-1, customer=self.customer, cluster=self.cluster, guid='test', gateway=True, fallback=True)
        self.assertEqual(self._get_state(), {(self.customer.pk, 0, 0, 0)})

    def test_ignore(self):

        CustomerPolicyState.objects.change_participants(1, customer=self.customer, cluster=self.cluster, guid='test', gateway=True, ignore_change=True)
        CustomerPolicyState.objects.change_participants(1, customer=self.customer, cluster=self.cluster, guid='test', gateway=True, ignore_change=True)
        CustomerPolicyState.objects.change_participants(-1, customer=self.customer, cluster=self.cluster, guid='test', gateway=True, ignore_change=True)
        CustomerPolicyState.objects.change_participants(-1, customer=self.customer, cluster=self.cluster, guid='test', gateway=True, ignore_change=True)

    def test_compare(self):

        self.customer.pexip_tenant_id = 'abc123'
        self.customer.save()
        customer2 = Customer.objects.create(title='Customer2')
        customer2.get_pexip_tenant_id()

        self.customer.get_pexip_tenant_id()
        ActiveCall.direct_objects.create(cluster=self.cluster, name='Test1', customer=self.customer)
        ActiveCall.direct_objects.create(cluster=self.cluster, name='Test2', customer=self.customer)
        ActiveCall.direct_objects.create(cluster=self.cluster, name='Test3', customer=self.customer)

        ActiveCall.direct_objects.create(cluster=self.cluster, name='Test4', customer=customer2)

        ActiveParticipant.direct_objects.create(cluster=self.cluster, guid='Testpart', customer=self.customer)
        ActiveParticipant.direct_objects.create(cluster=self.cluster, guid='Testpart2', customer=customer2)

        provider2, customer3 = self._create_separate_cluster_and_customer()

        stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            result = CustomerPolicyState.objects.compare_cluster_state(self.cluster)[0]
            CustomerPolicyState.objects.pretty_print_state_diff(self.cluster, result)
        finally:
            sys.stdout = stdout

        self.assertEqual(
            set(result.keys()), {None, self.customer.pexip_tenant_id, customer2.pexip_tenant_id}
        )

        self.assertEqual(set(result[self.customer.pexip_tenant_id].calls[0]), {'Test1', 'Test2', 'Test3'})
        self.assertEqual(set(result[None].calls[1]), {'VMR_1'})
        self.assertEqual(
            set(result[self.customer.pexip_tenant_id].participants[0]), {('Testpart', False)}
        )
        self.assertEqual(
            set(result[None].participants[1]), {('1c26be9c-6511-4e5c-9588-8351f8c3decd', False)}
        )

        ActiveParticipant.direct_objects.create(
            cluster=provider2.cluster, guid='Testpart3', customer=customer3
        )
        result2 = CustomerPolicyState.objects.compare_cluster_state(provider2.cluster)[0]
        self.assertEqual(set(result2.keys()), {customer3.pexip_tenant_id or None})
        self.assertEqual(set(result2[None].participants[0]), {('Testpart3', False)})
        self.assertEqual(
            set(result2[None].participants[1]), {('1c26be9c-6511-4e5c-9588-8351f8c3decd', False)}
        )

    def test_no_direct_change(self):
        with self.assertRaises(IntegrityError):
            ActiveParticipant.objects.all().update(customer=1)
        with self.assertRaises(IntegrityError):
            ActiveParticipant.objects.all().delete()
        with self.assertRaises(IntegrityError):
            ActiveCall.objects.all().update(customer=1)
        with self.assertRaises(IntegrityError):
            ActiveCall.objects.all().delete()


class TestRecheck(PolicyTestMixin):

    def test_recheck(self):

        CustomerPolicyState.objects.get_or_create(cluster=self.cluster, customer=self.customer)

        customer2 = Customer.objects.create(title='Customer2')
        customer2.get_pexip_tenant_id()

        result = CustomerPolicyState.objects.recheck(commit=False)
        self.assertTrue(result)

        result = CustomerPolicyState.objects.recheck(commit=True)
        self.assertTrue(result)

        result = CustomerPolicyState.objects.recheck(commit=True)
        self.assertFalse(result)

    def test_recheck_task(self):
        from ..tasks import recheck_policy_states
        recheck_policy_states()

    def test_remove_disconnected(self):

        part = ActiveParticipant.direct_objects.create(cluster=self.cluster, guid='activepart_local_extra', customer=None)
        call = ActiveCall.direct_objects.create(cluster=self.cluster, name='activecall_local_extra', customer=None)

        provider2, customer3 = self._create_separate_cluster_and_customer()
        call2 = ActiveCall.direct_objects.create(
            cluster=provider2.cluster, name='activecall_local_extra', customer=customer3
        )
        part2 = ActiveParticipant.direct_objects.create(
            cluster=provider2.cluster, guid='activepart_local_extra', customer=customer3
        )

        self._remove_disconnected(self.cluster, call, part)
        self._remove_disconnected(provider2.cluster, call2, part2)

    def _remove_disconnected(self, cluster, call, part):
        diff = CustomerPolicyState.objects.compare_cluster_state(cluster)[0]
        from ..tasks import remove_disconnected_policy_state_items

        self.assertEqual(
            ActiveParticipant.objects.filter(cluster=cluster, guid=part.guid).count(), 1
        )
        self.assertEqual(ActiveCall.objects.filter(cluster=cluster, name=call.name).count(), 1)

        self.assertTrue(any(x.participants.extra_local or x.calls.extra_local for x in diff.values()))

        remove_disconnected_policy_state_items(cluster.pk, json.loads(json.dumps(diff)))

        self.assertEqual(
            ActiveParticipant.objects.filter(cluster=cluster, guid=part.guid).count(), 0
        )
        self.assertEqual(ActiveCall.objects.filter(cluster=cluster, name=call.name).count(), 0)

    def test_add_missing(self):

        self.assertEqual(ActiveParticipant.objects.filter(guid='1c26be9c-6511-4e5c-9588-8351f8c3decd').count(), 0)
        self.assertEqual(ActiveCall.objects.filter(name='VMR_1').count(), 0)

        diff = CustomerPolicyState.objects.compare_cluster_state(self.cluster)[0]
        from ..tasks import add_missing_policy_state_items

        self.assertTrue(any(x.participants.extra_remote or x.calls.extra_remote for x in diff.values()))

        self.assertTrue(diff)

        add_missing_policy_state_items(self.cluster.pk, json.loads(json.dumps(diff)))

        self.assertEqual(ActiveParticipant.objects.filter(guid='1c26be9c-6511-4e5c-9588-8351f8c3decd').count(), 1)
        self.assertEqual(ActiveCall.objects.filter(name='VMR_1').count(), 1)
