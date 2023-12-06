import re
from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, List
from urllib.parse import urljoin

from django.conf import settings
from django.db import models, transaction

# Create your models here.
from django.utils.dateparse import parse_datetime
from django.utils.encoding import force_text
from django.utils.timezone import localtime, now
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField
from sentry_sdk import capture_exception

from customer.models import Customer
from endpoint.consts import MANUFACTURER, TASKSTATUS
from endpoint.models import CustomerSettings, Endpoint
from provider.exceptions import AuthenticationError, ResponseConnectionError, ResponseError
from roomcontrol.models import RoomControl, RoomControlTemplate
from shared.exceptions import format_exception
from shared.utils import maybe_update

TASK_ERROR_LIMIT = 20


class EndpointProvisionData(models.Model):

    configuration = JSONField()
    template = models.ForeignKey('EndpointTemplate', null=True, on_delete=models.SET_NULL)
    address_book = models.ForeignKey('address.AddressBook', null=True, on_delete=models.SET_NULL)
    branding_profile = models.ForeignKey('endpoint_branding.EndpointBrandingProfile', null=True, on_delete=models.SET_NULL)
    commands = JSONField()
    backup = models.SmallIntegerField(null=True, choices=((1, 'Backup'), (2, 'Restore')))
    passive = models.BooleanField(default=False)
    room_analytics = models.BooleanField(default=False, null=True)
    statistics = models.BooleanField(default=False)
    ca_certificates = models.BooleanField(default=False)
    events = models.BooleanField(default=False)
    dial_info = JSONField(null=True)
    password = models.CharField(max_length=100)
    clear_room_controls = models.BooleanField(default=False, null=True)
    room_controls = models.CharField(max_length=200, blank=True, null=True, default='')
    room_control_templates = models.CharField(max_length=200, blank=True, null=True, default='')
    room_controls_delete_operation = models.BooleanField(default=False, null=True)
    firmware = models.ForeignKey('EndpointFirmware', null=True, on_delete=models.SET_NULL)
    firmware_url = models.CharField(max_length=200)
    force_firmware = models.BooleanField(default=False)

    extra_properties = JSONField(_('Anpassningar för respektive åtgärd'), null=True, blank=True)

    def get_room_controls(self):
        if not self.room_controls:
            return RoomControl.objects.none()
        return RoomControl.objects.filter(id__in=self.room_controls.split(','))

    def get_room_control_templates(self):
        if not self.room_control_templates:
            return RoomControlTemplate.objects.none()
        return RoomControlTemplate.objects.filter(id__in=self.room_control_templates.split(','))

    def get_properties(self, key: str) -> Dict[str, Any]:
        properties = self.extra_properties or {}
        return properties.get(key) or {}

    def get_actions(self):

        actions = []
        for k in (
            'configuration',
            'backup',
            'commands',
            'events',
            'password',
            'address_book',
            'firmware',
            'passive',
            'room_controls',
            'statistics',
            'template',
            'ca_certificates',
            'dial_info',
            'room_analytics',
        ):
            if getattr(self, k):
                actions.append(k)
        if self.firmware_url and not self.firmware_id:
            actions.append('firmware')
        if self.branding_profile_id:
            actions.append('branding')
        if (self.room_control_templates or self.clear_room_controls) and 'room_controls' not in actions:
            actions.append('room_controls')

        if self.extra_properties and self.extra_properties.get('repeat', {}).get('enable'):
            actions.append('repeat')

        return actions

    def save(self, *args, **kwargs):
        if self.firmware_id:
            self.firmware_url = self.firmware.get_absolute_url()
        return super().save(*args, **kwargs)


class EndpointProvisionManager(models.Manager):

    def provision(self, customer, endpoints, user, constraint=None, delay=False, **data):
        obj = self.prepare(
            customer=customer, endpoints=endpoints, user=user, constraint=constraint, **data
        )
        if delay:
            return obj, ''
        return obj, obj.run()

    def run_single(self, customer, endpoint, user, constraint=None, delay=False, **data):
        obj = self.prepare(
            customer=customer, endpoints=[endpoint], user=user, constraint=constraint, **data
        )
        if delay:
            return obj, ''
        return obj.run_single(endpoint)

    def prepare(self, customer, endpoints, user, constraint=None, **data):

        if isinstance(endpoints, Endpoint):
            endpoints = [endpoints]

        if data:
            data_obj: EndpointProvisionData = EndpointProvisionData.objects.create(**data)
        else:
            data_obj = None

        obj: EndpointProvision = self.create(customer=customer, user=str(user), data=data_obj, constraint=constraint)
        obj.endpoints.add(*endpoints)

        return obj

    def log(self, endpoint, action, user, result='OK', error=False):

        obj = self.create(customer=endpoint.customer, user=user)

        for task in obj.prepare_tasks(endpoint, extra_actions=[action]):
            if error:
                task.fail(result)
            else:
                task.complete(result)
            return task

    def update_constraint_times(self):
        for customer in Customer.objects.distinct().filter(endpoints__isnull=False):
            self.update_constraint_times_for_customer(customer)

    def update_constraint_times_for_customer(self, customer: Customer):
        c_settings = CustomerSettings.objects.get_for_customer(customer)

        per_timezone = defaultdict(list)

        with transaction.atomic():
            # group per timezone
            for task in (
                EndpointTask.objects.select_for_update(of=('self',))
                .filter(
                    provision__customer=customer,
                    provision__constraint=EndpointProvision.NIGHT,
                )
                .filter(
                    status__in=(EndpointTask.TASKSTATUS.QUEUED, EndpointTask.TASKSTATUS.PENDING),
                )
                .select_related('endpoint')
            ):

                if not task.endpoint:
                    continue

                per_timezone[task.endpoint.timezone].append(task)

            # update schedule
            for timezone, tasks in per_timezone.items():

                next_night = c_settings.get_next_night_start(timezone=timezone)
                night_end = c_settings.get_next_night_end(timezone=timezone)

                filtered_task_ids = [
                    t.pk
                    for t in tasks
                    if not t.ts_schedule_attempt or t.ts_schedule_attempt > night_end
                ]

                if filtered_task_ids:
                    EndpointTask.objects.filter(pk__in=filtered_task_ids).update(
                        ts_schedule_attempt=next_night
                    )


class EndpointProvision(models.Model):

    NIGHT = 10
    CONSTRAINTS = (
        (None, 'None'),
        (NIGHT, 'Natt'),
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)

    endpoints = models.ManyToManyField(Endpoint)

    constraint = models.SmallIntegerField(choices=CONSTRAINTS, default=None, null=True, blank=True)

    data = models.ForeignKey(EndpointProvisionData, null=True, on_delete=models.SET_NULL)

    user = models.CharField(max_length=100)

    ts_created = models.DateTimeField(default=now)

    objects = EndpointProvisionManager()

    def check_constraint(self, ts=None, timezone=None):
        if not self.constraint:
            return True

        if self.constraint == self.NIGHT:
            c_settings = CustomerSettings.objects.get_for_customer(self.customer)
            if c_settings.is_night(ts=ts, timezone=timezone):
                return True

        return False

    def prepare_tasks(self, endpoint, extra_actions=None) -> List['EndpointTask']:

        existing_qs = self.endpointtask_set.filter(endpoint=endpoint)
        if existing_qs.exists():
            return list(existing_qs)

        actions = self.data.get_actions() if self.data else []
        if extra_actions:
            actions.extend(extra_actions)

        ts_schedule_attempt = None
        if self.data and self.data.get_properties('schedule').get('ts'):
            ts = self.data.extra_properties['schedule']['ts']
            ts_schedule_attempt = parse_datetime(ts)

        if self.constraint == self.NIGHT:
            c_settings = CustomerSettings.objects.get_for_customer(self.customer)
            if not c_settings.is_night(ts_schedule_attempt, timezone=endpoint.timezone):
                ts_schedule_attempt = c_settings.get_next_night_start(
                    ts_schedule_attempt, timezone=endpoint.timezone
                )

        result = []
        for action in actions:
            cur: EndpointTask = EndpointTask.objects.create(
                customer=self.customer,
                endpoint=endpoint,
                provision=self,
                data=self.data,
                action=action,
                ts_schedule_attempt=ts_schedule_attempt,
            )
            result.append(cur)

        # Connect room controls. TODO: set activate state
        if self.data and self.data.room_controls:
            endpoint.room_controls.add(*list(self.data.get_room_controls()))
        if self.data and self.data.room_control_templates:
            endpoint.room_control_templates.add(*list(self.data.get_room_control_templates()))
            
        return result

    def prepare_all_tasks(self):
        result = []
        for endpoint in self.endpoints.all():
            tasks = self.prepare_tasks(endpoint)

            result.append((endpoint, tasks))

        return result

    def run(self, sync=False):

        result = defaultdict(list)
        errors = defaultdict(list)

        from endpoint.tasks import queue_pending_endpoint_tasks

        async_endpoints = []
        for endpoint, tasks in self.prepare_all_tasks():

            if not self.check_constraint(timezone=endpoint.timezone):
                continue

            if not endpoint.has_direct_connection:
                continue

            if not sync:
                async_endpoints.append(endpoint.id)
                continue

            for task in tasks:

                try:
                    cur = task.run()
                except ResponseError as e:
                    errors[endpoint.pk].append(e)
                else:
                    result[endpoint.pk].append(cur)

        if async_endpoints:
            queue_pending_endpoint_tasks.delay(endpoint_ids=async_endpoints)

        return result, errors

    def run_single(self, endpoint):

        if not self.check_constraint(timezone=endpoint.timezone):
            return None, 'Waiting for night time'

        for task in self.prepare_tasks(endpoint):
            try:
                return task, task.run()
            except ResponseError as e:
                raise e
        raise ValueError('Invalid task')


class EndpointTask(models.Model):

    TASKSTATUS = TASKSTATUS

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    provision = models.ForeignKey(EndpointProvision, null=True, on_delete=models.SET_NULL)
    data = models.ForeignKey(EndpointProvisionData, null=True, on_delete=models.SET_NULL)

    # Don't reset endpoint_id on delete to allow for timescaledb-compression:
    endpoint = models.ForeignKey(
        Endpoint, on_delete=models.DO_NOTHING, null=True, db_constraint=False
    )
    endpoint_id_bak = models.IntegerField(null=True)

    action = models.CharField(max_length=100)
    status = models.SmallIntegerField(choices=tuple((ts.value, ts.name) for ts in TASKSTATUS),
                                      default=TASKSTATUS.PENDING)

    tries = models.SmallIntegerField(default=0)

    error = models.TextField()
    result = models.TextField()

    ts_created = models.DateTimeField(default=now)
    ts_last_change = models.DateTimeField(null=True, default=now)
    ts_last_attempt = models.DateTimeField(null=True)
    ts_schedule_attempt = models.DateTimeField(null=True)
    ts_completed = models.DateTimeField(null=True)

    api = None

    @property
    def is_slow(self):
        if self.action in ('statistics', 'firmware'):
            return True
        return False

    @property
    def supports_passive(self):
        unsupported = {'statistics', 'backup', 'password'}
        return self.action not in unsupported

    class Meta:
        ordering = ('-ts_created',)
        index_together = (
            ('ts_last_change', 'ts_created'),
            ('status', 'ts_created'),
        )

    def run(self):
        if not self.endpoint:
            return self.fail('No endpoint')

        if self.ts_schedule_attempt and self.ts_schedule_attempt > (
            CustomerSettings._override_localtime or now()
        ):
            return self.add_error('Trying to run before schedule')

        if not self.provision.check_constraint(timezone=self.endpoint.timezone):
            return self.add_error('Trying to run outside of constraint')

        if not self.endpoint.has_direct_connection:
            if self.endpoint.connection_type == self.endpoint.CONNECTION.PASSIVE:
                if not self.supports_passive:
                    return self.fail('This task is not supported in passive mode')
            return self.add_error(
                'No direct connection is available. Command is added to the queue and will be run '
                'the next time the system is online'
            )

        data = self.data
        endpoint = self.endpoint
        action = self.action

        if not data:
            return self.fail('No data for action {}'.format(action))
        if not action:
            return self.fail('No action')

        if not endpoint.is_cisco and action in {'branding', 'room_control'}:
            return self.fail('Not supported')

        start = now()

        extra_properties = self.data.extra_properties or {}
        api = self.endpoint.get_api()

        api.active_task = self

        try:
            result = ''
            if action == 'configuration':
                # completion in method handler
                return api.set_configuration(data.configuration, task=self)
            elif action == 'template':
                if data.template_id:
                    if data.template.settings:
                        result = api.set_configuration(data.template.settings, task=self)
                    if data.template.commands:
                        result += api.run_multiple_commands(data.template.commands)
            elif action == 'commands':
                cmd_result: List[str] = []
                for command in (data.commands or ()):
                    if isinstance(command, dict) and command.get('command'):
                        cur = api.run_command(command['command'], command.get('arguments') or {}, command.get('body'))
                        cmd_result.append(force_text(cur))
                result = '\n'.join(cmd_result)
            elif action == 'backup':
                result = endpoint.backup(sync=True)
            elif action == 'events':
                result = api.set_events()
            elif action == 'dial_info':
                # completion in method handler
                return api.set_dial_info(data.dial_info, task=self)
            elif action == 'branding':
                result = '\n̈́'.join(
                    force_text(r) for r in api.update_branding(data.branding_profile)
                )
            elif action == 'ca_certificates':
                c_settings = CustomerSettings.objects.get_for_customer(self.customer)
                result = api.add_ca_certificates(c_settings.ca_certificates)
            elif action == 'password':
                result = api.set_password(
                    endpoint.username,
                    data.password,
                    validate_current_password=extra_properties.get('password', {}).get(
                        'validate_current_password'
                    )
                    or True,
                )
            elif action == 'passive':
                result = api.set_passive_provisioning(
                    chain=extra_properties.get('passive', {}).get('chain'), task=self
                )
            elif action == 'statistics':
                calls = api.update_statistics(1000)
                result = '{} imported calls, {} ignored'.format(sum(1 for c in calls if c), sum(1 for c in calls if not c))
            elif action == 'address_book':
                result = api.set_address_book(data.address_book, task=self)
            elif action == 'repeat':
                self.repeat()
                result = ''
            elif action == 'room_controls':
                if self.endpoint.is_poly:
                    return self.fail('Not supported.')

                lines = []
                if data.clear_room_controls:
                    lines.append(api.clear_room_controls(all=True))
                room_controls = self.data.get_room_controls().filter(customer=self.endpoint.customer)
                room_control_templates = self.data.get_room_control_templates().filter(customer=self.endpoint.customer)
                if self.data.room_controls_delete_operation:
                    lines.append(
                        api.clear_room_controls(
                            controls=room_controls, templates=room_control_templates
                        )
                    )
                else:
                    macro_enabled = False
                    try:
                        if api.get_macro_status():
                            macro_enabled = True
                    except ResponseError:
                        pass

                    if not macro_enabled:
                        lines.append(
                            api.set_configuration(
                                [{'key': ['Macros', 'Mode'], 'value': 'On'}], task=self
                            )
                        )
                        lines.append(api.run_command(['Macros', 'Runtime', 'Start']))
                        if not settings.TEST_MODE:
                            self.delay()
                            return self.add_error('Macro runtime was not enabled. Wait for startup')

                    lines.append(
                        api.set_room_controls(
                            controls=room_controls, templates=room_control_templates
                        )
                    )

                    self.delay(replace_action='room_controls_restart')

                lines.append(
                    api.set_room_controls_features(
                        controls=room_controls, templates=room_control_templates
                    )
                )
                result = '\n'.join(force_text(r) for r in lines)
            elif action == 'room_controls_restart':
                result = api.run_command(['Macros', 'Runtime', 'Restart'])
            elif action == 'room_analytics':

                room_analytics = extra_properties.get('room_analytics') or {}
                if endpoint.personal_system and not room_analytics.get('allow_personal'):
                    if room_analytics.get('head_count') or room_analytics.get('presence'):
                        return self.fail('Room analytics is not allowed on personal systems')

                configuration = api.get_room_analytics_configuration(
                    room_analytics.get('head_count'),
                    room_analytics.get('presence'),
                    detect_support=True,
                )
                if configuration:
                    result = api.set_configuration(configuration, task=self)
                else:
                    return self.fail('Not supported by system')
            elif action == 'firmware':
                result = api.install_firmware(data.firmware.get_absolute_url() if data.firmware else data.firmware_url)
            else:
                raise ValueError('Invalid action: {}'.format(action))
        except (AuthenticationError, ResponseConnectionError) as e:
            self.add_error(e)
            raise
        except ResponseError as e:
            self.add_error(e)
            return e.get_message()
        except Exception as e:
            capture_exception()
            self.add_error(e, duration=(now() - start).total_seconds())
            raise e
        else:
            result = force_text(result or '')
            if 'Result status="Error"' in result:
                if 'status="OK"' not in result:
                    return self.fail(result)
                errors = re.findall(r'<Reason>(.*?)</Reason>', result)
                self.add_error(
                    'Some errors did occur: {}'.format(
                        '\n'.join(set(e for e in errors)) or 'check logs'
                    )
                )
            if self.status != TASKSTATUS.ERROR:
                self.complete(result)
            return result
        finally:
            api.active_task = None

    def delay(self, replace_action=None, countdown=5):
        return EndpointTask.objects.create(
            endpoint=self.endpoint,
            provision=self.provision,
            data=self.data,
            action=replace_action or self.action,
            ts_schedule_attempt=(CustomerSettings._override_localtime or now())
            + timedelta(seconds=countdown),
            ts_created=self.ts_created,
        )

    def save(self, *args, **kwargs):
        if not self.endpoint_id_bak:
            self.endpoint_id_bak = self.endpoint_id
        if not self.customer_id and self.endpoint_id:
            self.customer = self.endpoint.customer

        if self.status in (TASKSTATUS.PENDING, TASKSTATUS.QUEUED) and not self.endpoint:
            self.status = TASKSTATUS.CANCELLED

        self.ts_last_change = now()

        super().save(*args, **kwargs)

    def cancel(self):
        if self.status == TASKSTATUS.COMPLETED:
            raise ValueError('Cant cancel an already completed task')
        self.status = TASKSTATUS.CANCELLED
        self.error += 'Cancelled by user\n'
        self.ts_completed = now()
        self.save()

    def retry(self):
        if self.status in (TASKSTATUS.PENDING, TASKSTATUS.QUEUED):
            raise ValueError('Cant retry a pending task')
        self.ts_last_attempt = None
        self.ts_completed = None
        self.status = TASKSTATUS.PENDING
        self.error += '{}\n{}: Manually retried\n'.format(self.error, now()).lstrip()
        self.save()

    def repeat(self):
        """Repeat all tasks for this endpoint provision"""
        tasks = EndpointTask.objects.filter(
            provision=self.provision,
            endpoint=self.endpoint,
            status__in=[
                TASKSTATUS.COMPLETED,
                TASKSTATUS.ERROR,
            ],
        ).exclude(ts_completed__gt=now() - timedelta(hours=4))

        c_settings = CustomerSettings.objects.get_for_customer(self.customer_id)
        if c_settings.is_night(timezone=self.endpoint.timezone):
            ts_schedule_attempt = now()
        else:
            ts_schedule_attempt = c_settings.get_next_night_start(timezone=self.endpoint.timezone)

        tasks.update(status=TASKSTATUS.PENDING, ts_schedule_attempt=ts_schedule_attempt)
        self.ts_schedule_attempt = c_settings.get_next_night_start(timezone=self.endpoint.timezone)
        self.save(update_fields=['ts_schedule_attempt'])

    def commit_changes(self):
        """Commit changes to endpoint after task has completed. Passive only for now"""
        api = self.endpoint.get_api()

        if self.action == 'password':
            self.endpoint.password = self.data.password
            self.endpoint.save(update_fields=['password'])
        elif self.action == 'dial_info':
            api.save_dial_info(self.data.dial_info or {})
        elif self.action == 'branding':
            api.save_provisioned_object(
                'branding',
                {'id': self.data.branding_profile.pk, 'title': str(self.data.branding_profile)},
                replace=True,
            )
        elif self.action == 'ca_certificates':
            c_settings = CustomerSettings.objects.get_for_customer(self.endpoint.customer_id)
            command, certificates = api.get_add_ca_certificates_command(c_settings.ca_certificates)
            api.save_provisioned_certificates(certificates)

    def complete_passive(self, result=None):

        try:
            self.commit_changes()
        except Exception as e:
            if settings.DEBUG or settings.TEST_MODE:
                raise
            self.add_error(
                'Task was provisioned, but local data could not be saved: {}'.format(
                    format_exception(e)
                )
            )

        return self.complete(result=result)

    def complete(self, result=None):
        self.ts_last_attempt = now()
        self.ts_completed = now()
        if self.action != 'repeat':
            self.status = TASKSTATUS.COMPLETED
        if result is not None:
            self.result = (self.result + '\n' if self.result else '') + result
        self.save()

    def fail(self, result=None):
        self.ts_last_attempt = now()
        self.ts_completed = now()
        self.status = TASKSTATUS.ERROR
        if result is not None:
            self.result = (self.result + '\n' if self.result else '') + result
        self.save()
        return 'Failed: {}'.format(result) if result else 'Failed.'

    def add_error(self, error, duration: float = None):
        self.ts_last_attempt = now()
        if duration:
            message = '{} (after {}s)'.format(format_exception(error), duration)
        else:
            message = format_exception(error)

        cur_error = '{}: {}\n'.format(localtime().replace(microsecond=0), message)
        self.error += cur_error
        self.tries += 1
        if self.tries > TASK_ERROR_LIMIT:
            self.fail('Too many retries. Giving up.')
        elif self.status == self.TASKSTATUS.QUEUED:
            self.status = self.TASKSTATUS.PENDING
        self.save()
        return 'Error: {}'.format(format_exception(error))


class EndpointTargetState(models.Model):

    endpoint = models.ForeignKey(
        Endpoint,
        on_delete=models.DO_NOTHING,
        null=True,
        db_constraint=False,
    )

    TYPES = (
        ('configuration', 'Configuration'),
        ('status', 'Status'),
    )
    type = models.CharField(max_length=100, choices=TYPES)
    values = JSONField(null=True)
    ts_last_update = models.DateTimeField(null=True)

    objects: models.Manager['EndpointTargetState'] = models.Manager()

    class Meta:
        unique_together = ('endpoint', 'type')

    @classmethod
    @transaction.atomic
    def apply(cls, endpoint: Endpoint, type: str, values: List[dict]) -> 'EndpointTargetState':

        assert type in ('configuration', 'status')

        target_state, created = EndpointTargetState.objects.select_for_update(
            of=('self',)
        ).get_or_create(endpoint=endpoint, type=type)

        target_values = target_state.values or {}

        for configuration in values:
            key = ' '.join(configuration['key'])
            if configuration['value'] is None:
                target_values.pop(key, None)
            else:
                target_values[key] = str(configuration['value'])

        target_state.values = target_values
        target_state.ts_last_update = now()
        target_state.save(update_fields=['values', 'ts_last_update'])

        return target_state


class EndpointFirmware(models.Model):

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    manufacturer = models.SmallIntegerField(choices=tuple((m.value, m.name) for m in MANUFACTURER))
    orig_file_name = models.CharField(max_length=200)
    is_global = models.BooleanField(default=False, blank=True)
    model = models.CharField(max_length=200)
    version = models.CharField(max_length=200)
    ts_created = models.DateTimeField(default=now)
    file = models.FileField(upload_to='firmware')

    def delete(self, *args, **kwargs):
        should_delete = (
            not EndpointFirmware.objects.exclude(pk=self.pk).filter(file=self.file).exists()
        )
        result = super().delete(*args, **kwargs)
        if should_delete:
            self.file.delete(save=False)
        return result

    def copy(self, **kwargs):
        obj = EndpointFirmware.objects.get(pk=self.pk)
        obj.pk = obj.id = None
        obj.ts_created = now()
        maybe_update(obj, kwargs)
        return obj

    @property
    def title(self):
        return self.file.name

    def get_absolute_url(self):
        return urljoin('https://{}/'.format(settings.EPM_HOSTNAME), self.file.url)


class EndpointTemplate(models.Model):

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    name = models.CharField(_('Namn'), max_length=100, blank=True)
    manufacturer = models.SmallIntegerField(choices=tuple((m.value, m.name) for m in MANUFACTURER), default=MANUFACTURER.CISCO_CE)
    model = models.CharField(_('Produktnamn'), max_length=200)
    ts_created = models.DateTimeField(default=now, editable=False)
    settings = JSONField(
        blank=True, help_text='JSON array of objects [{"key": ["Audio", "Volume"], "value": "1"}]'
    )
    commands = JSONField(
        null=True,
        blank=True,
        help_text='JSON array of objects [{"command": ["HttpFeedback", "Register"], "arguments": {"FeedbackSlot": "1"}, "body": "<file content or null>"}]',
    )

    def __str__(self):
        return self.name


class EndpointProvisionedObjectHistory(models.Model):
    endpoint = models.ForeignKey(Endpoint, on_delete=models.CASCADE, null=True, db_constraint=False)

    ts_created = models.DateTimeField(default=now, editable=False)
    ts_replaced = models.DateTimeField(null=True, editable=False)

    type = models.CharField(max_length=200)
    data = JSONField(null=True, blank=True)
