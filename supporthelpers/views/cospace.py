from typing import Type

from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.http import Http404, HttpResponse, JsonResponse
from django.core.mail import EmailMultiAlternatives
from django.utils.timezone import now
from django.urls import reverse
from collections import  OrderedDict
from datetime import date

from organization.models import CoSpaceUnitRelation, OrganizationUnit
from provider.forms import CoSpaceAccessMethodForm
from ui_message.invite import format_message_content
from provider.exceptions import NotFound, ResponseError
from ..forms import (
    CoSpaceForm,
    CoSpaceChangeListForm,
    CoSpaceBasicForm,
    CoSpaceAutoForm,
    CoSpaceFormMixin,
)
from statistics.models import Call

from urllib.parse import urljoin

from django.utils.translation import ugettext_lazy as _

from django.conf import settings
from provider.models.acano import CoSpace
from meeting.models import Meeting
from ui_message.models import Message

from .mixins import ItemListMixin, TrackChangesMixin
from customer.view_mixins import LoginRequiredMixin, CustomerMixin
from cdrhooks.models import Hook
from recording.models import AcanoRecording



DEFAULT_DOMAIN = getattr(settings, 'DEFAULT_ACANO_DOMAIN', None)


class CoSpaceIndexView(LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'cospace/cospace.html'

    def dispatch(self, request, *args, **kwargs):
        self.customer = self._get_customer(self.request)

        if self._get_api().provider.is_pexip:
            return redirect('pexip_cospaces_details', **self.kwargs)

        if self.customer:
            self.cospace = self._get_cospace()
            if not self.cospace:
                raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def _get_cospace(self):
        cospace_id = self.kwargs.get('cospace_id') or self.request.GET.get('cospace')

        if cospace_id:
            cospace = CoSpaceForm(cospace=cospace_id).load(customer=self._get_customer(self.request))
            self.customer = self._check_tenant_customer(cospace.get('tenant'), change=True)
            return cospace

        return {}

    def get_populated_member_permissions(self):

        api = self._get_api()
        members = api.get_members(self.cospace['cospace'], include_user_data=True)

        permission_labels = OrderedDict([
            ('canDestroy', _('Ta bort')),
            ('canAddRemoveMember', _('Lägg till/Ta bort medlemmar')),
            ('canChangeName', _('Ändra namn')),
            ('canChangeUri', _('Ändra uri')),
            ('canChangeCallId', _('Ändra call id')),
            ('canChangePasscode', _('Ändra passcode')),
            ('canRemoveSelf', _('Ta bort sig själv')),
            ('canChangeNonMemberAccessAllowed', _('Medlemsaccess')),
            ('canChangeScope', _('Ändra accessmethod')),
            ('isModerator', _('Styra kamera/ljud')),
        ])

        if api.provider.software_version.startswith('2'):
            permission_labels.update(
                [
                    ('canPostMessage', _('Ändra meddelande')),
                    ('canDeleteAllMessages', _('Ta bort alla meddelanden')),
                ]
            )

        for m in members:
            m['permissionTypes'] = OrderedDict()
            for permission_type, permission_value in list(m['permissions'].items()):
                if permission_type not in permission_labels:
                    continue

                m['permissionTypes'][permission_type] = {
                    'label': permission_labels[permission_type],
                    'permitted': permission_value
                }

        return members

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.customer
        context['PREFIX_FOR_MATCH_ALL'] = ItemListMixin.PREFIX_FOR_MATCH_ALL

        if customer:
            context['customer'] = customer
            provider = customer.get_provider()
            context['provider'] = provider
            assert provider.is_acano

            api = self._get_api()
            cospace = self.cospace
            if cospace:

                context['members'] = self.get_populated_member_permissions()

                context['calls'], count = api.get_clustered_calls(cospace=cospace['cospace'], include_legs=True)

                context['booked_meeting'] = Meeting.objects.filter(provider_ref2=cospace['cospace']).order_by('-ts_created').first()

                def _populate_web_url(access_method):
                    if access_method.get('callId'):
                        return {
                            **access_method,
                            'web_url': api.get_web_url(cospace=access_method),
                            'sip_uri': api.get_sip_uri(cospace=access_method),
                        }
                    return access_method

                context['access_methods'] = [
                    _populate_web_url(am)
                    for am in api.get_cospace_accessmethods(cospace['cospace'], include_data=True)
                ]

                try:
                    hook = Hook.objects.get(provider=provider, provider_ref=cospace['cospace'])
                except Hook.DoesNotExist:
                    hook = None
                else:
                    context['hook'] = hook

                all_calls = Call.objects.filter(cospace_id=cospace['cospace']).order_by('-ts_start')
                todays_calls = all_calls.filter(ts_start__gte=now().replace(hour=0, minute=0))
                context['latest_calls'] = todays_calls[:10] if todays_calls.count() >= 3 else all_calls[:3]
                context['organization_unit'] = OrganizationUnit.objects.filter(cospaces__provider_ref=cospace['cospace']).first()

                context['recordings'] = AcanoRecording.objects.filter(cospace_id=cospace['id'])

            context['cospace'] = cospace
            context['web_url'] = api.get_web_url(cospace=cospace)
            context['sip_uri'] = api.get_sip_uri(cospace=cospace)

            if cospace.get('owner_id'):
                context['owner'] = self._get_api().get_user(cospace.get('owner_id'))
                context['owner_org_unit'] = OrganizationUnit.objects.filter(users__user_jid=context['owner']['jid']).first()

        if not context.get('error'):
            context['message'] = self.request.session.pop('cospaces_message', None)

        context['has_organization'] = settings.ENABLE_ORGANIZATION

        return context

    def _add_all_members(self, api, cospace, customer, filter=None):

        members = []
        for user in api._iter_all_users(tenant_id=customer.acano_tenant_id):

            jid = user.findtext('userJid')
            if filter and filter not in jid:
                continue
            members.append(jid)

        return self._add_members(api, cospace, customer, members)

    def _add_members(self, api, cospace, customer, members):

        call_leg_profile = None
        try:
            existing = CoSpace.objects.get(provider=api.cluster, provider_ref=cospace['cospace'])
        except CoSpace.DoesNotExist:
            pass
        else:
            if existing.moderator_ref:
                guest_call_leg, moderator_call_leg = api._get_webinar_call_legs()
                call_leg_profile = moderator_call_leg

        error = []
        for member in members:
            if '@' not in member and DEFAULT_DOMAIN:
                member = '{}@{}'.format(member, DEFAULT_DOMAIN)

            try:
                api.add_member(cospace['cospace'], member,
                    can_add_remove_members=True, can_remove_self=True, can_destroy=True,
                    can_delete_messages=True, call_leg_profile=call_leg_profile)
            except Exception:
                error.append(member)

        if error:
            error = 'Kunde inte lägga till användare: {}'.format(', '.join(error))
            return self.render_to_response(self.get_context_data(error=error))

    def post(self, request, *args, **kwargs):

        api = self._get_api()

        cospace = self.cospace
        customer = self.customer

        if request.POST.get('remove_cospace'):
            api.delete_cospace(request.POST['remove_cospace'])
            return redirect('{}?customer={}'.format(request.path, customer.pk))
        elif request.POST.get('form_action') == 'remove_members':
            for member in request.POST.getlist('remove_member'):
                api.remove_member(cospace['cospace'], member)
        elif request.POST.get('form_action') == 'update_permissions':
            members = self._get_api().get_members(self.cospace['cospace'])

            for member in members:
                names_of_new_permissions = request.POST.getlist('permission_{}'.format(member['user_id']))
                current_permissions = member['permissions']
                updated_permissions = { name: ('true' if name in names_of_new_permissions else 'false') for name in iter(list(current_permissions.keys()))}

                if updated_permissions != current_permissions:
                    api.update_member(cospace['cospace'], member['id'], **updated_permissions)
        elif 'organization_unit_full_name' in self.request.POST:
            organization_unit_full_name = self.request.POST.get('organization_unit_full_name')
            CoSpaceUnitRelation.objects.create_and_assign_organization_unit_to_cospace(organization_unit_full_name, cospace['cospace'], customer=self.customer)
        elif self.request.POST.get('add_member', False):
            member = self.request.POST.get('add_member')
            if member:
                if member.startswith(ItemListMixin.PREFIX_FOR_MATCH_ALL):
                    response = self._add_all_members(api, cospace, customer, filter=member.split(ItemListMixin.PREFIX_FOR_MATCH_ALL)[1])
                else:
                    response = self._add_members(api, cospace, customer, [member])

                if response:
                    return response

        elif request.POST.get('form_action') == 'new_call':
            call_id = api.add_call(cospace['cospace'], name=request.POST.get('name', cospace['title']))
            return redirect(reverse('call_handler', args=[call_id]) + '?customer={}'.format(self._get_customer().pk))

        elif request.POST.get('clear_chat'):
            try:
                self._get_api().clear_chat(cospace['cospace'])
            except (NotFound, AttributeError):
                request.session['cospaces_message'] = str(_('Den här funktionen finns endast i CMS fram till v2.9'))
            else:
                request.session['cospaces_message'] = str(_('Chatten är nu rensad'))
            return redirect(request.get_full_path())

        request.session['cospaces_message'] = str(_('Åtgärden slutfördes utan problem'))
        return redirect(request.get_full_path())


class CoSpaceFormView(LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'cospace/edit.html'

    def _get_cospace(self):
        cospace_id = self.kwargs.get('cospace_id') or self.request.GET.get('cospace')

        if cospace_id:
            return CoSpaceForm(cospace=cospace_id).load(customer=self._get_customer(self.request))
        return {}

    def get_context_data(self, **kwargs):

        from numberseries.models import NumberSeries

        context = super().get_context_data(**kwargs)
        customer = self._get_customer(self.request)

        if not context.get('error'):
            context['message'] = self.request.session.pop('cospaces_message', None)

        if not customer:
            return context

        context['customer'] = customer
        provider = customer.get_provider()
        assert provider.is_acano

        number_series = NumberSeries.objects.get_for('provider', provider)
        if number_series.prefix.all():
            context['number_series'] = number_series

        cospace = self._get_cospace()

        context['cospace'] = cospace
        if provider.software_version.startswith('2'):
            context['has_clear_chat'] = True

        if cospace.get('id') and 'access_method_forms' not in context:
            access_method_forms = []
            for am in self._get_api().get_cospace_accessmethods(cospace['cospace']):
                if am['id'] == cospace.get('moderator_access_method'):
                    continue
                access_method_forms.append(
                    CoSpaceAccessMethodForm(
                        prefix='am-{}'.format(am['id']),
                        initial=CoSpaceAccessMethodForm.load(am),
                        cospace_id=cospace['id'],
                        access_method_id=am['id'],
                    )
                )

            context['access_method_forms'] = access_method_forms

        if 'form' not in context:
            FormClass = self.get_edit_form_class(cospace)
            context['form'] = FormClass(initial=context['cospace'], customer=customer)

        if cospace.get('id'):
            context['members'] = self._get_api().get_members(cospace['cospace'])

            if not context['cospace'].get('ts_auto_remove'):
                try:
                    context['cospace']['ts_auto_remove'] = Meeting.objects.filter(provider_ref2=cospace['cospace'])[0].ts_stop_corrected
                except IndexError:
                    pass

            try:
                hook = Hook.objects.get(provider=provider, provider_ref=cospace['cospace'])
            except Hook.DoesNotExist:
                hook = None
            else:
                context['hook'] = hook

            context['organization_unit'] = OrganizationUnit.objects.filter(cospaces__provider_ref=cospace['cospace']).first()

        return context

    def get_edit_form_class(self, cospace) -> Type[CoSpaceFormMixin]:
        if cospace.get('auto_generated'):
            return CoSpaceAutoForm
        elif not cospace.get('editable_accessmethods'):
            return CoSpaceBasicForm
        else:
            return CoSpaceForm

    def _edit_cospace(self, api, cospace, customer):
        FormClass = self.get_edit_form_class(cospace)
        form = FormClass(self.request.POST, cospace=cospace.get('cospace'), customer=customer)

        is_valid = form.is_valid()
        am_is_valid = True

        access_method_forms = []

        errors = []

        if cospace.get('cospace'):
            for am in self._get_api().get_cospace_accessmethods(cospace['cospace']):
                if am['id'] == cospace.get('moderator_access_method'):
                    continue
                am_form = CoSpaceAccessMethodForm(
                    self.request.POST,
                    prefix='am-{}'.format(am['id']),
                    cospace_id=cospace['id'],
                    access_method_id=am['id'],
                )
                if not am_form.is_valid():
                    am_is_valid = False
                    form.add_error('__all__', _('En accessmethod kunde inte valideras'))
                access_method_forms.append(am_form)

        if is_valid:
            try:
                cospace, error = form.save(creator=self.request.user.email)

            except ResponseError as e:
                errors.append(str(e))
        else:
            errors.append(str(form.errors))

        if am_is_valid:
            for am_form in access_method_forms:
                try:
                    am_form.save(customer)
                except ResponseError as e:
                    am_form.add_error('name', e)
                    errors.append(str(e))

        if errors:
            return self.render_to_response(
                self.get_context_data(form=form, error='\n'.join(errors))
            )

        return redirect(urljoin(reverse('cospaces_details', args=[cospace]), '?customer={}'.format(customer.pk)))

    def post(self, request, *args, **kwargs):

        api = self._get_api()

        cospace = self._get_cospace()
        customer = self._get_customer(self.request)

        if request.POST.get('remove_cospace'):
            api.delete_cospace(request.POST['remove_cospace'])
            return redirect('{}?customer={}'.format(request.path, customer.pk))
        elif request.POST.get('form_action') == 'edit_cospace':
            response = self._edit_cospace(api, cospace, customer)
            if response:
                return response

        request.session['cospaces_message'] = str(_('Åtgärden slutfördes utan problem'))
        return redirect(request.get_full_path())


class CospaceInviteView(LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'cospace/invite.html'
    default_message_type = 'acano_cospace'

    sent_emails = None

    def dispatch(self, request, *args, **kwargs):
        if kwargs.get('_internal_api_use'):
            return self
        return super().dispatch(request, *args, **kwargs)

    def _get_cospace(self):
        cospace_id = self.kwargs.get('cospace_id') or self.request.GET.get('cospace')

        if cospace_id:
            result = CoSpaceForm(cospace=cospace_id).load(customer=self._get_customer(self.request))
            if not result:
                raise Http404()
            return result
        return {}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        cospace = self._get_cospace()
        customer = self._get_customer(self.request)

        context['provider'] = customer.get_provider()

        message = self._get_invite_message(customer, cospace.get('cospace') or cospace.get('id'))

        context['invite_title'] = message['title']
        context['invite_message'] = message['content']
        context['attachment'] = message['attachment']
        context['invite_plain'] = message['plain']

        context['invite_sent'] = self.request.session.pop('cospace_invite_sent', None)

        context['web_url'] = self._get_api().get_web_url(cospace=cospace)
        context['dialstring'] = self._get_api().get_sip_uri(cospace=cospace)

        context['initial_email'] = self.request.GET.get('email', '')

        context['sender_email'] = settings.SERVER_EMAIL

        context['meeting_type'] = Message.TYPES[self._get_invite_message_type()]
        context['meeting_types'] = [m for m in Message.TYPES if m[0] != Message.TYPES.outlook_welcome]

        context['cospace'] = cospace
        if self._get_api().provider.is_pexip:
            context['cospace_url'] = '{}?customer={}'.format(reverse('pexip_cospaces_details', args=[cospace['id']]), customer.pk)
        else:
            context['cospace_url'] = '{}?customer={}'.format(reverse('cospaces_details', args=[cospace['id']]),
                                                         customer.pk)
        context['cms_user'] = self._get_cms_user()

        return context

    def _get_cms_user(self):
        return None

    def _get_invite_message_type(self):
        try:
            meeting_type = int(self.request.GET.get('message_type') or Message.TYPES[self.default_message_type])
            return Message.TYPES.get_key(meeting_type)
        except Exception:
            return self.default_message_type

    def _get_invite_message(self, customer, cospace_id):

        return Message.objects.get_for_cospace(customer, cospace_id, message_type=self._get_invite_message_type())

    def send_invite(self, emails):

        api = self._get_api()
        customer = api.customer
        cospace = self._get_cospace()

        emails = [e.strip() for email in emails for e in email.split(',') if e.strip()]

        message = self._get_invite_message(customer, cospace['cospace'])
        subject = self.request.POST.get('subject', '').strip() or message['title']
        if emails:
            if self.request.user.email:
                headers = {'Reply-To': self.request.user.email}
            else:
                headers = {}
            msg = EmailMultiAlternatives(subject, message['plain'], settings.SERVER_EMAIL, emails, headers=headers)
            msg.attach_alternative(format_message_content(subject, message['content']), "text/html")

            if message['attachment']:
                msg.attach_file(message['attachment'].path)

            msg.send()

            self.send_email_done(emails)

    def send_email_done(self, emails):
        self.request.session['cospace_invite_sent'] = True

    def post(self, request, *args, **kwargs):

        if request.POST.get('form_action') == 'invite':

            emails = self.request.POST.get('emails', '').split('\n')

            response = self.send_invite(emails)
            if response:
                return response

        return redirect(request.get_full_path())


class CoSpaceListView(ItemListMixin, LoginRequiredMixin, CustomerMixin, TemplateView):
    template_name = 'cospace/list.html'

    def dispatch(self, request, *args, **kwargs):
        if not self._get_customer().get_provider():
            return redirect('/')

        super_result = super().dispatch(request, *args, **kwargs)
        cospace_id = request.GET.get('cospace_id', '')

        if cospace_id and not cospace_id.startswith(ItemListMixin.PREFIX_FOR_MATCH_ALL):
            return redirect(reverse('cospaces_details', args=[cospace_id]) + '?customer={}'.format(self.customer.pk))
        if request.GET.get('export_to_excel'):
            if self._get_api().cluster.is_pexip:
                return self._export_to_excel_pexip(
                    request.GET.get('filter'),
                    request.GET.get('organization_unit'),
                    request.GET.get('type'),
                )
            return self._export_to_excel(
                request.GET.get('filter'), request.GET.get('organization_unit')
            )

        if request.GET.get('ajax'):
            result = {}
            self.populate_items_context(result, request.GET.get('cospace_id', ''), items_key='cospaces')
            return JsonResponse(result)

        return super_result

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self._get_customer(self.request)

        if customer:
            context['customer'] = customer
            provider = customer.get_provider()
            assert provider.is_acano or provider.is_pexip

        if not context.get('error'):
            context['message'] = self.request.session.pop('cospaces_message', None)

        context['has_organization'] = settings.ENABLE_ORGANIZATION

        return context

    def get_items(self, api, q, offset, tenant):
        return api.find_cospaces(q=q, tenant=self.customer.acano_tenant_id, offset=offset)

    def filter_items_for_org_unit(self, items, org_units):

        ids = [item.get('id') for item in items if item.get('id')]
        valid_ids = CoSpaceUnitRelation.objects.filter(provider_ref__in=ids, unit__in=org_units).values_list('provider_ref', flat=True)

        return [item for item in items if item.get('id') in valid_ids]

    def create_url_for_cospace(self, cospace):
        return reverse('cospaces_details', args=[cospace['id']]) + '?customer={}&cospace={}'.format(self.customer.pk, cospace['id'])

    def _export_to_excel(self, filter, organization_unit_id=None):
        import xlwt
        response = HttpResponse(content_type="application/ms-excel")
        response['Content-Disposition'] = 'attachment; filename=spaces-{}.xls'.format(date.today())

        wb = xlwt.Workbook()
        ws = wb.add_sheet('sheet 1')

        api = self._get_api()
        cospace_elements = api._iter_all_cospaces(tenant_id=api.get_tenant_id(), filter=filter)

        cospace_identities = [{'id': cospace_element.get('id')} for cospace_element in cospace_elements]

        headers = [str(h) for h in [
            _('Namn'),
            _('URI'),
            _('Call ID'),
            _('Ägare'),
            _('Organisationsenhet'),
            _('Autogenererat'),
            _('Webblänk'),
        ]]

        for index, header in enumerate(headers):
            ws.write(0, index, header)

        if organization_unit_id:
            organization_unit = OrganizationUnit.objects.get(pk=organization_unit_id)
            cospace_identities = self.filter_items_for_org_unit(cospace_identities, organization_unit.get_descendants(include_self=True))

        from datastore.models.acano import CoSpace

        cached_cospaces = {c.cid: c.to_dict()
                for c in CoSpace.objects.filter(
                    provider=api.provider,
                    cid__in=[cc.get('id') for cc in cospace_identities]
                )}

        org_units = {c.provider_ref: c.unit.full_name
            for c in CoSpaceUnitRelation.objects.select_related('unit').filter(
                provider_ref__in=[cc.get('id') for cc in cospace_identities]
            )}

        for index, cospace_identity in enumerate(cospace_identities):
            row = index + 1
            cospace_id = cospace_identity.get('id')

            if cospace_id in cached_cospaces:
                cospace = cached_cospaces[cospace_id]
            else:
                cospace = api.get_cospace(cospace_id)

            cospace_name = cospace.get('name')

            ws.write(row, 0, cospace_name)
            ws.write(row, 1, cospace.get('uri'))
            ws.write(row, 2, cospace.get('callId') or cospace.get('call_id'))
            ws.write(row, 3, cospace.get('ownerJid') or cospace.get('owner'))
            ws.write(row, 4, org_units.get(cospace.get('id')))
            ws.write(row, 5, 'x' if cospace.get('auto_generated') or cospace.get('autoGenerated') else '')

            if cospace:
                url = api.get_web_url(cospace=cospace)
                ws.write(row, 6, xlwt.Formula('HYPERLINK("{url}")'.format(url=url)))

        wb.save(response)
        return response

    def _export_to_excel_pexip(self, filter, organization_unit_id=None, type=None):
        import xlwt

        response = HttpResponse(content_type="application/ms-excel")
        response['Content-Disposition'] = 'attachment; filename=spaces-{}.xls'.format(date.today())

        wb = xlwt.Workbook()
        ws = wb.add_sheet('sheet 1')

        from provider.ext_api.pexip import PexipAPI
        from datastore.models.pexip import Conference

        api: PexipAPI = self._get_api()  # type: ignore

        conferences = Conference.objects.search_active(
            provider=api.cluster,
            q=filter,
            tenant=api.get_tenant_id(),
            org_unit=organization_unit_id,
            type=type,
        )

        if organization_unit_id:
            conferences = conferences.prefetch_related(
                'organization_unit', 'organization_unit__parent'
            )
        conferences = conferences.prefetch_related('aliases')

        headers = [
            str(h)
            for h in [
                _('Namn'),
                _('URI'),
                _('Call ID'),
                _('Alias'),
                _('Ägare'),
                _('Organisationsenhet'),
                _('Webblänk'),
            ]
        ]

        y = 0
        for index, header in enumerate(headers):
            ws.write(y, index, header)

        for conference in conferences:
            y += 1

            cur_data = conference.to_dict()

            ws.write(y, 0, conference.name)
            ws.write(y, 1, cur_data['uri'])
            ws.write(y, 2, conference.call_id)
            ws.write(y, 3, ', '.join(a['alias'] for a in cur_data['aliases']))
            ws.write(y, 4, conference.primary_owner_email_address)
            ws.write(
                y, 5, str(conference.organization_unit) if conference.organization_unit else ''
            )
            ws.write(  # TODO remove secret?
                y, 6, xlwt.Formula('HYPERLINK("{url}")'.format(url=conference.web_url))
            )

        wb.save(response)
        return response


class CoSpaceChangeListView(TrackChangesMixin, TemplateView):

    template_name = 'cospace/changes.html'
    form_class = CoSpaceChangeListForm
    excel_export_basename = 'cospace-change'

