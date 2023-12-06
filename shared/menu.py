from django.urls import reverse, resolve
from django.utils.translation import ugettext as _, ngettext


class MenuBuilder:

    def __init__(self, cur_path, cur_class, customer=None):
        self.cur_path = cur_path
        self.cur_class = cur_class
        self.customer = customer

    def get_menu_items(self):

        subitems = [
        ]
        yield [reverse('users'), _('Användare'), subitems]

        subitems = [
        ]
        yield [reverse('cospaces'), ngettext('Mötesrum', 'Mötesrum', 2), subitems]

        subitems = [
        ]
        yield [reverse('calls'), _('Möten'), subitems]

        subitems = [
        ]
        yield [reverse('meeting_debug_list'), _('Bokade möten'), subitems]

        subitems = [
        ]
        yield [reverse('stats'), _('Statistik'), subitems]

    def get_menu(self):
        '''
        returns tuple with
        (menu_items, sub_items_for_active_item)

        menu_items = (url, title, is_active, subitems)
        '''

        show_subitems = []

        result = []

        customer_suffix = '?customer={}'.format(self.customer.pk) if self.customer else ''

        # check current view
        def is_current_view(url):
            try:
                m = resolve(url)
            except Exception:
                return False
            if not m:
                return False
            if m.func.__class__ != self.cur_class:
                return False

            return m.func == self.cur_class.as_view

        menu_items = list(self.get_menu_items())

        urls = [u for u, t, s in menu_items]
        urls.extend([u for m in menu_items for u, t in m[2]])

        if urls:
            # longest matching
            try:
                active = sorted(((len(u), u) for u in urls if self.cur_path.startswith(u) or is_current_view(u)), reverse=True)[0][1]
            except IndexError:
                active = None
        else:
            active = None

        for url, parent, subitems in menu_items:

            cur_active = (url == active)

            if not cur_active and subitems:
                cur_active = any(u == active for u, t in subitems)

            if cur_active:
                show_subitems = subitems

            result.append([url + customer_suffix, parent, cur_active, subitems])

        subitems = []
        for url, title in show_subitems:
            cur_active = (url == active)
            subitems.append([url + customer_suffix, title, cur_active, []])

        return result, subitems


class MenuMixin:

    def get_menu(self):

        if not self.request.user.is_authenticated:
            return [], []

        customer = self._get_customer() if hasattr(self, '_get_customer') else None

        return MenuBuilder(cur_path=self.request.path, cur_class=self.__class__, customer=customer).get_menu()
