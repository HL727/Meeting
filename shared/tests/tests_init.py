from django.test import TransactionTestCase

from customer.models import Customer
from ui_message.models import Message


class UpgradeInstallationTestCase(TransactionTestCase):

    def test_upgrade_installation(self):
        from shared.management.commands.upgrade_installation import Command

        Command().run_from_argv(['manage.py', 'upgrade_installation', '-v0'])

        self.assertTrue(Customer.objects.all())
        self.assertTrue(Message.objects.all())
