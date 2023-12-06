from django.test import TestCase
from django.conf import settings


class NumberSerieTestCase(TestCase):

    def test_numbers(self):

        if 'numberseries' not in settings.INSTALLED_APPS:
            return

        from .models import NumberSeries

        result = []
        for _i in range(10):
            cur = NumberSeries.objects.use_next('account')
            result.append(int(cur))

        self.assertEqual(result, list(range(1, 11)))

        result = []
        for _i in range(10):
            cur = NumberSeries.objects.use_next('account2')
            result.append(int(cur))

        self.assertEqual(result, list(range(1, 11)))

        self.assertEqual(NumberSeries.objects.use_next('account'), '%04d' % 11)

        cur = NumberSeries.objects.use_next('account3', default='AB-01-1')
        self.assertEqual(cur, 'AB-01-1')

        result = []
        for _i in range(120):

            cur = NumberSeries.objects.use_next('account3')
            result.append(cur)

        self.assertIn('AB-01-9', result)
        self.assertNotIn('AB-01-10', result)
        self.assertIn('AB-02-1', result)

        self.assertIn('AB-10-1', result)
        self.assertNotIn('AB-100-1', result)

        prefix = NumberSeries.objects.get_for('account3').get_prefix()
        prefix.last_number = 'AB-999-9'
        prefix.save()
        self.assertRaises(ValueError, NumberSeries.objects.use_next, 'account3')
