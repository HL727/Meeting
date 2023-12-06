from django.utils.timezone import now
from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.http import Http404, HttpResponse
from django.urls import reverse
from datetime import date

from django.utils.translation import ugettext_lazy as _

from django.conf import settings

from organization.models import UserUnitRelation, OrganizationUnit
from statistics.models import Leg
from supporthelpers.views.mixins import ItemListMixin, TrackChangesMixin
from supporthelpers.forms import CoSpaceForm, UserChangeListForm
from customer.view_mixins import LoginRequiredMixin, CustomerMixin
from .cospace import CospaceInviteView


DEFAULT_DOMAIN = getattr(settings, 'DEFAULT_ACANO_DOMAIN', None)


class UserMixin(CustomerMixin):

    def _get_user(self):
        user_id = self.kwargs.get('user_id') or self.request.GET.get('user')

        if user_id:
            customer = self._get_customer()
            user = customer.get_api().get_user(user_id)
            self.customer = self._check_tenant_customer(user.get('tenant'), change=True)
            return user
        return {}

    def dispatch(self, request, *args, **kwargs):

        self._get_customer(request)
        self.user = self._get_user()

        return super().dispatch(request, *args, **kwargs)

    def _get_user_cospace(self):
        return self._get_api().get_user_private_cospace(self.user['id'])


class UserListView(ItemListMixin, LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'base_vue.html'

    def get(self, request, *args, **kwargs):
        self.customer = self._get_customer(request)
        user_id = request.GET.get('user_id', '')
        if user_id and not user_id.startswith(ItemListMixin.PREFIX_FOR_MATCH_ALL):
            return redirect(reverse('user_details', args=[user_id]) + '?customer={}'.format(self.customer.pk))

        if request.GET.get('export_to_excel'):
            return self._export_to_excel(request.GET.get('filter'), request.GET.get('organization_unit'))
        return super().get(request, *args, **kwargs)

    def filter_items_for_org_unit(self, items, org_units):

        jids = [item.get('jid') for item in items if item.get('jid')]
        valid_jids = UserUnitRelation.objects.filter(user_jid__in=jids, unit__in=org_units).values_list('user_jid', flat=True)

        return [item for item in items if item.get('jid') in valid_jids]

    def _export_to_excel(self, filter, organization_unit_id=None):
        import xlwt
        response = HttpResponse(content_type="application/ms-excel")
        response['Content-Disposition'] = 'attachment; filename=users-{}.xls'.format(date.today())

        wb = xlwt.Workbook()
        ws = wb.add_sheet('sheet 1')

        api = self._get_api()
        user_elements = api._iter_all_users(tenant_id=api.get_tenant_id(), filter=filter)

        user_identities = list()
        for user_element in user_elements:
            jid = None if isinstance(user_element, dict) else user_element.findtext('./userJid', '')
            user_identities.append({
                'id': user_element.get('id'),
                'jid': jid
            })

        headers = [str(h) for h in [
            _('Namn'),
            _('E-postadress'),
            _('LDAP-användarnamn'),
            _('Videoadress till CMA'),
            _('Videoadress till personligt VMR'),
            _('Samtals-ID till personligt VMR'),
            _('Webblänk till personligt VMR'),
            _('Organisationsenhet'),
        ]]

        for index, header in enumerate(headers):
            ws.write(0, index, header)

        if organization_unit_id:
            organization_unit = OrganizationUnit.objects.get(pk=organization_unit_id)
            user_identities = self.filter_items_for_org_unit(user_identities, organization_unit.get_descendants(include_self=True))

        from datastore.models import acano as ds

        cached_users = {u.uid: u.to_dict()
                for u in ds.User.objects.filter(
                    provider=api.provider,
                    uid__in=[uu.get('id') for uu in user_identities])}

        org_units = {ur.user_jid: ur.unit for ur in UserUnitRelation.objects.all().select_related('unit', 'unit__parent', 'unit__parent__parent')}
        ous = dict(ds.User.objects.all().values_list('username', 'ldap_ou__name'))

        for index, user_identity in enumerate(user_identities):
            row = index + 1
            user_id = user_identity.get('id')
            personal_vmr = {}

            if user_id in cached_users:
                user = cached_users[user_id]

                try:
                    personal_vmr = ds.CoSpace.objects.get(owner__uid=user_id, provider=api.provider, is_auto=True, is_active=True).to_dict()
                except ds.CoSpace.DoesNotExist:
                    pass
            else:
                user = api.get_user(user_id)

            user_name = user.get('name')

            if not personal_vmr:

                for cospace in api.get_user_cospaces(user_id, include_cospace_data=True):
                    if cospace.get('auto_generated'):
                        personal_vmr = cospace
                        break

            personal_vmr_call_id = personal_vmr.get('callId')

            ws.write(row, 0, user_name)
            ws.write(row, 1, user.get('email'))
            ws.write(row, 2, user.get('ldap_username', ''))
            ws.write(row, 3, user.get('jid'))
            if personal_vmr.get('uri'):
                ws.write(row, 4, api.get_sip_uri(cospace=personal_vmr))
            ws.write(row, 5, personal_vmr_call_id)

            url = api.get_web_url(cospace=personal_vmr)
            ws.write(row, 6, xlwt.Formula('HYPERLINK("{url}")'.format(url=url)))

            ws.write(row, 7, org_units[user.get('jid')].full_name if org_units.get(user.get('jid')) else ous.get(user.get('jid')) or '')

        wb.save(response)
        return response


class UserDetails(LoginRequiredMixin, UserMixin, TemplateView):

    template_name = 'users/user.html'

    def dispatch(self, request, *args, **kwargs):

        if self._get_api().provider.is_pexip:
            return redirect('pexip_user_details', **self.kwargs)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self._get_customer(self.request)

        if customer:
            context['customer'] = customer
            provider = customer.get_provider()
            context['provider'] = provider
            assert provider.is_acano

            user = self.user
            if user:
                context['cospaces'] = self._get_api().get_user_cospaces(user['id'], include_cospace_data=True)

                user_jid = user['jid']

                context['first_call_date'] = Leg.objects.get_first_call_date_for_user(user_jid)
                context['last_call_date'] = Leg.objects.get_last_call_date_for_user(user_jid)

                user_unit_relation = UserUnitRelation.objects.filter(user_jid=user_jid).first()
                if user_unit_relation:
                    context['organization_unit'] = user_unit_relation.unit

                context['user_cospace'] = self._get_user_cospace()


                context['calls'] = [self._get_api().get_call(leg['call']) \
                    for leg in self._get_api().get_call_legs(filter=user['jid'], tenant=customer.acano_tenant_id)[0]]

            context['cms_user'] = user

        context['sender_email'] = self.request.user.email or settings.SERVER_EMAIL

        context['has_organization'] = settings.ENABLE_ORGANIZATION

        if not context.get('error'):
            context['message'] = self.request.session.pop('users_message', None)

        return context

    def _add_cospaces(self, api, user, customer, cospaces):
        error = []
        user_jid = user['jid']
        for cospace_id in cospaces:

            try:
                api.add_member(
                    cospace_id,
                    user_jid,
                    can_add_remove_members=True,
                    can_remove_self=True,
                    can_destroy=True,
                    can_delete_messages=True,
                    is_moderator=True,
                )
            except Exception:
                error.append(cospace_id)

        if error:
            error = 'Kunde inte lägga till användare: {}'.format(', '.join(error))
            return self.render_to_response(self.get_context_data(error=error))

    def post(self, request, *args, **kwargs):
        api = self._get_api()

        user = self.user
        customer = self._get_customer(self.request)

        if request.POST.get('form_action') == 'remove':
            for cospace in request.POST.getlist('remove_cospace'):
                # TODO find relation id
                api.remove_member(cospace, user['id'])
        elif request.POST.get('form_action') == 'add_cospaces':
            cospaces = self.request.POST.getlist('cospaces_to_add')
            response = self._add_cospaces(api, user, customer, cospaces)

            if response:
                return response
        elif 'organization_unit_full_name' in self.request.POST:
            organization_unit_full_name = self.request.POST.get('organization_unit_full_name')
            self.create_and_assign_organization_unit_to_user(organization_unit_full_name, user['jid'], customer)

        request.session['users_message'] = str(_('Åtgärden slutfördes utan problem'))
        return redirect(request.get_full_path())

    def create_and_assign_organization_unit_to_user(self, organization_unit_full_name, user_jid, customer):
        UserUnitRelation.objects.filter(user_jid=user_jid).delete()

        if organization_unit_full_name:
            unit, _ = OrganizationUnit.objects.get_or_create_by_full_name(organization_unit_full_name, customer=customer)
            UserUnitRelation.objects.get_or_create(user_jid=user_jid, unit=unit)


class UserInviteView(UserMixin, CospaceInviteView):

    default_message_type = 'acano_user'

    def _get_cospace(self):
        cospace = self._get_user_cospace()
        if not cospace:
            raise Http404()
        return CoSpaceForm(cospace=cospace['id']).load(customer=self._get_customer(self.request))

    def _get_invite_message(self, customer, cospace_id):
        from ui_message.models import Message

        message = Message.objects.get_for_cospace(customer, cospace_id, self._get_invite_message_type())
        if not message['content']:
            return super()._get_invite_message(customer, cospace_id)
        return message

    def send_email_done(self, emails):
        user = self._get_cms_user()
        if not user.email:
            return

        for email in emails:
            if user.email in email:
                user.ts_instruction_email_sent = now()
                user.save()
                break
        self.sent_emails = emails
        self.request.session['cospace_invite_sent'] = True

    def _get_cms_user(self):
        from datastore.models import acano as ds
        return ds.User.objects.get_user(self._get_api(), self._get_user()['id'])


class UserChangeListView(TrackChangesMixin, TemplateView):

    template_name = 'users/changes.html'
    form_class = UserChangeListForm

    excel_export_basename = 'user-change'

