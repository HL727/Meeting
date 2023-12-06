from datetime import datetime, timedelta
from typing import Dict, Optional, Sequence
from xml.etree import ElementTree as ET

from axes.handlers.proxy import AxesProxyHandler
from django.conf import settings
from django.db import transaction
from django.http import Http404, HttpResponse
from django.utils.encoding import force_bytes, force_text
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from sentry_sdk import capture_exception

from endpoint.consts import TASKSTATUS
from endpoint.ext_api.parser.tms_event import TMSPostedDocumentEvent, TMSSoapEvent
from endpoint.models import CustomerAutoRegisterIpNet, CustomerSettings, Endpoint, Q
from endpoint_data.models import EndpointCurrentState
from endpoint_provision.models import EndpointTask
from provider.exceptions import AuthenticationError, ResponseError
from shared.exceptions import format_exception

DEFAULT_HEARTBEAT_INTERVAL = 7 * 60


def check_endpoint_customer(request, customer_secret: str, _log):
    if AxesProxyHandler.is_locked(request, {}):
        return HttpResponse('Too many authentication attempts', status=403)

    if not customer_secret and settings.EPM_EVENT_CUSTOMER_SECRET:
        return HttpResponse('<Forbidden error="missing_customer_key" />', status=403)

    customer = None

    if customer_secret:
        customer = Endpoint.objects.get_customer_for_key(customer_secret, raise_exception=False)
        if not customer:
            # TODO remove + customer_secret
            _log(event='tms_auth_error', error='Invalid customer url key: ' + customer_secret)
            AxesProxyHandler.user_login_failed(
                sender=Endpoint,
                credentials={'username': 'key-{}'.format(customer_secret)},
                request=request,
            )
            from audit.models import AuditLog

            AuditLog.objects.store_request(request, 'Invalid customer provisioning key')
            raise Http404()

    return customer


@csrf_exempt
def tms(request, customer_secret=None, endpoint_secret=None, endpoint_serial=None):
    from debuglog.models import EndpointCiscoProvision

    def _log(endpoint=None, **extra):
        try:
            event = extra.pop('event', None) or 'tms'
            EndpointCiscoProvision.objects.store(
                ip=request.META.get('REMOTE_ADDR'),
                content=request.body,
                event=event,
                endpoint=endpoint,
                **extra
            )
        except Exception:
            capture_exception()

    user_agent = request.META.get('HTTP_USER_AGENT', '')
    if user_agent.startswith('FileTransport '):
        # Poly endpoint
        from endpoint_provision.views_poly_provision import poly_directory_root_passive_provision

        return poly_directory_root_passive_provision(
            request,
            customer_secret=customer_secret,
            endpoint_secret=endpoint_secret,
            endpoint_serial=endpoint_serial,
        )

    customer = check_endpoint_customer(request, customer_secret, _log)
    if isinstance(customer, HttpResponse):
        return customer

    chained_hostname = request.META.get('HTTP_X_CHAINED_EXTERNALMANAGER')
    if chained_hostname in (settings.EPM_HOSTNAME, settings.HOSTNAME):
        return HttpResponse('<Error message="Invalid chaining of External Manager" />', status=403)

    valid = True
    if b'"http://www.tandberg.net/2004/11/SystemManagementService/"' not in request.body:
        valid = False
    if b'<PostEvent' not in request.body:
        valid = False
    if not valid:
        _log()
        return HttpResponse('Event type not found', status=404)

    try:
        xml, endpoint = _handle_postevent(
            request, customer=customer, endpoint_secret=endpoint_secret
        )
        _log(endpoint)
        return HttpResponse(xml, content_type='text/xml')
    except AuthenticationError:
        _log(event='tms_auth_error', error='Invalid endpoint secret key/MAC-address/serial')
        return HttpResponse('<Error message="Invalid identification" />', status=403)
    except Exception as e:
        _log(event='tms_response_error', error=str(e))
        raise


def _handle_postevent(request, customer, endpoint_secret=None):
    try:
        event = TMSSoapEvent(request.body, customer=customer, endpoint_secret=endpoint_secret)
        event.get_identification()
    except AuthenticationError:
        raise

    try:
        endpoint = event.handle_event()
    except AuthenticationError:
        raise
    except Endpoint.DoesNotExist:
        endpoint = None

    ip = request.META.get('REMOTE_ADDR', '127.0.0.1')

    is_initial = event.get_event_type() in ('Register', 'Boot')
    if is_initial and not endpoint:
        if customer:
            endpoint = event.create_endpoint(customer, request_ip=ip)
        else:
            net = CustomerAutoRegisterIpNet.objects.get_for_ip(ip)
            if net:
                endpoint = event.create_endpoint(net.customer, request_ip=ip)

    if endpoint:
        with transaction.atomic():
            xml = get_endpoint_tms_response(endpoint, is_initial=is_initial, ip=ip, lock_tasks=True)
    else:
         xml = format_tms_xml_response()

    return xml, endpoint


def get_passive_endpoint_tasks(
    endpoint: Endpoint,
    lock_tasks: bool = False,
    constraint_ts: datetime = None,
    ignore_constraints: bool = False,
):

    tasks = EndpointTask.objects\
        .filter(endpoint=endpoint, status__in=(TASKSTATUS.PENDING, TASKSTATUS.QUEUED)) \
        .filter(Q(ts_schedule_attempt__isnull=True) | Q(ts_schedule_attempt__lte=now()))\
        .select_related('provision')\
        .order_by('ts_created')

    if endpoint.has_direct_connection:  # wait at least 10 mins to run in in active mode to get feedback
        tasks = tasks.filter(ts_created__lt=now() - timedelta(minutes=10))

    if lock_tasks:
        tasks = tasks.select_for_update(skip_locked=True, of=('self',))

    tasks = list(tasks)

    for t in tasks:  # preload
        t.endpoint = endpoint
        t.customer = endpoint.customer
        t.provision.customer = endpoint.customer

    if not ignore_constraints:
        tasks = [
            t
            for t in tasks
            if t.provision.check_constraint(ts=constraint_ts, timezone=t.endpoint.timezone)
        ]  # TODO cache

    return tasks


def get_endpoint_tms_response(
    endpoint: Endpoint,
    is_initial: bool = False,
    ip: str = None,
    lock_tasks: bool = False,
    constraint_ts: datetime = None,
    ignore_constraints: bool = False,
):

    tasks = get_passive_endpoint_tasks(
        endpoint=endpoint,
        lock_tasks=lock_tasks,
        constraint_ts=constraint_ts,
        ignore_constraints=ignore_constraints,
    )

    data_args = get_endpoint_tms_response_context(
        endpoint, tasks, is_initial=is_initial, remote_ip=ip, ignore_constraints=True
    )  # constraint already checked
    xml = format_tms_xml_response(**data_args)

    if any(data_args.values()):
        try:
            from debuglog.models import EndpointCiscoProvision
            EndpointCiscoProvision.objects.store(ip=ip, content=xml, endpoint=endpoint,
                                                 event='tms_response')
        except Exception:
            capture_exception()
            if settings.DEBUG or settings.TEST_MODE:
                raise

    for t in tasks:
        if not t.supports_passive:
            continue

        t.complete_passive(
            '<Status>Sent to endpoint using passive provision. Completion information is not supported</Status>'
        )
        if t.action == 'events':
            endpoint.ts_feedback_events_set = now()
            endpoint.save(update_fields=['ts_feedback_events_set'])

    return xml


def get_endpoint_tms_response_context(
    endpoint: Endpoint,
    tasks: Sequence[EndpointTask],
    is_initial: bool = False,
    constraint_ts: datetime = None,
    ignore_constraints: bool = False,
    allow_chained_service=True,
    remote_ip: str = None,
) -> Dict[str, str]:

    configuration = []
    commands = []
    software = []
    documents_xml = ''
    calendar_xml = ''
    command_xml = ''
    configuration_xml = ''

    heartbeat_interval = 45 if endpoint.is_active else None

    api = endpoint.get_api()
    tasks = list(tasks)
    for t in tasks:
        if not ignore_constraints and not t.provision.check_constraint(
            ts=constraint_ts, timezone=t.endpoint.timezone
        ):  # TODO cache
            continue
        if t.endpoint.connection_type == Endpoint.CONNECTION.PASSIVE and not t.supports_passive:
            continue

        data = t.data
        action = t.action
        extra_properties = data and data.extra_properties or {}

        if action == 'configuration':
            configuration.extend(data.configuration)
        elif action == 'room_analytics':
            room_analytics = extra_properties.get('room_analytics') or {}

            if endpoint.personal_system and not room_analytics.get('allow_personal'):
                if room_analytics.get('head_count') or room_analytics.get('presence'):
                    room_analytics = {}  # disable bulk provisioning

            configuration.extend(
                api.get_room_analytics_configuration(
                    room_analytics.get('head_count'),
                    room_analytics.get('presence'),
                )
            )
        elif action == 'template':
            if data.template_id and data.template.settings:
                configuration.extend(data.template.settings)
            if data.template_id and data.template.commands:
                commands.extend(data.template.commands)
        elif action == 'dial_info':
            dial_info = data.dial_info or {}
            if dial_info.get('current'):
                dial_info.update(api.get_saved_dial_info())

            configuration.extend(
                api.get_update_dial_info_configuration(
                    dial_info, api.customer, versions=[endpoint.status.software_version]
                )
            )
        elif action == 'branding':
            # TODO CE 9.9 supports xCommand UserInterface Branding Fetch
            commands.extend(api.get_update_branding_commands(data.branding_profile))
        elif action == 'commands':
            commands.extend(data.commands)
        elif action == 'password':
            commands.append(
                api.get_set_password_command(
                    endpoint.username,
                    data.password,
                    validate_current_password=extra_properties.get('password', {}).get(
                        'validate_current_password'
                    )
                    or True,
                )
            )
        elif action == 'ca_certificates':
            c_settings = CustomerSettings.objects.get_for_customer(endpoint.customer_id)
            command, _certificates = api.get_add_ca_certificates_command(c_settings.ca_certificates)
            commands.append(command)
        elif action == 'address_book':
            configuration.extend(api.get_update_address_book_configuration(data.address_book))
        elif action == 'passive':
            if extra_properties.get('passive', {}).get('chain'):
                api.set_chained_passive_provisioning()

            configuration.extend(api.get_passive_provisioning_configuration())
        elif action == 'room_controls':
            if data.clear_room_controls:
                commands.extend(api.get_clear_room_controls_commands(all=True))

            configuration.extend(api.get_room_controls_feature_configuration(
                controls=data.get_room_controls(),
                templates=data.get_room_control_templates(),
                clear=data.room_controls_delete_operation
            ))

            if data.room_controls_delete_operation:
                commands.extend(api.get_clear_room_controls_commands(controls=data.get_room_controls(), templates=data.get_room_control_templates()))
            else:
                macro_enabled = False
                try:
                    if api.get_macro_status():
                        macro_enabled = True
                except ResponseError:
                    pass

                if not macro_enabled:
                    configuration.append({'key': ['Macros', 'Mode'], 'value': 'On'})
                    commands.append({'command': ['Macros', 'Runtime', 'Start']})

                commands.extend(api.get_room_controls_commands(controls=data.get_room_controls(), templates=data.get_room_control_templates()))  # TODO FilesToDownload?

                commands.append({'command': ['Macros', 'Runtime', 'Restart']})
                t.delay(replace_action='room_controls_restart', countdown=5)
                heartbeat_interval = 10
        elif action == 'room_controls_restart':
            commands.append({'command': ['Macros', 'Runtime', 'Restart']})
        elif action == 'repeat':
            t.repeat()
        elif action == 'events':
            commands.append(
                api.get_update_events_command()
            )

        elif action == 'firmware':
            firmware_url = t.data.firmware.get_absolute_url() if t.data.firmware else t.data.firmware_url
            software = ['''
            <Package>
                <URL>{}</URL>
            </Package>
            <Feedback>
                <URL>{}</URL>
            </Feedback>
            '''.format(
                    firmware_url,
                    endpoint.get_document_url(),
                )
            ]
        else:
            pass  # ?

    c_settings = CustomerSettings.objects.get_for_customer(endpoint.customer_id)

    if c_settings.enable_obtp and settings.EPM_ENABLE_OBTP:
        calendar = [
            api._get_booking_putxml_content(b.as_dict('html')) for b in endpoint.get_bookings()
        ]
    else:
        calendar = []

    passive_response_root = None

    if endpoint.get_external_manager_url() and allow_chained_service:
        try:
            passive_response_root = api.get_external_passive_response(remote_ip=remote_ip)
        except Exception:
            if settings.TEST_MODE or settings.DEBUG:
                raise

    if passive_response_root:
        try:
            calendar.extend(
                [
                    ET.tostring(node, encoding='unicode')
                    for node in api.get_external_calendar_items(passive_response_root)
                ]
            )
        except Exception:
            pass

    if calendar:
        calendar_xml = '<Bookings xmlns="http://www.cisco.com/TelePresence/Bookings/1.0">{}</Bookings>'.format('\n'.join(calendar))

    if is_initial or endpoint.should_update_provision_document or configuration or commands:
        documents_xml = (
            '<DocumentToPost><Location>/Status</Location><URL>{path}</URL></DocumentToPost>'
            '<DocumentToPost><Location>/Configuration</Location><URL>{path}</URL></DocumentToPost>'
        ).format(
            path=endpoint.get_document_url(),
        )

    configuration_root = ET.Element('Configuration')

    if passive_response_root:
        configuration_root.extend(api.get_external_configuration(passive_response_root))

    if configuration:
        configuration_root.extend(list(api._get_configuration_xml(configuration)))

    if len(configuration_root) and endpoint.status.software_version.lower().startswith('tc'):
        configuration_xml = ET.tostring(configuration_root, encoding='unicode').replace(
            '<Configuration>', '<Configuration xmlns="http://www.tandberg.com/XML/CUIL/2.0">'
        )
    elif len(configuration_root):
        configuration_xml = ET.tostring(configuration_root, encoding='unicode').replace(
            '<Configuration>', '<Configuration internal="true" xmlns="">'
        )

    command_root = ET.Element('Command', {'xmlns': ''})

    if passive_response_root:
        command_root.extend(list(api.get_external_commands(passive_response_root)))

    if commands:

        for command in commands:
            command_root.extend(list(api._get_run_command_xml(**command)))

    if len(command_root):
        command_xml = ET.tostring(command_root, encoding='unicode')

    return dict(
        Configuration=configuration_xml,
        Command=command_xml,
        Calendar=calendar_xml,
        DocumentsToPost=documents_xml,
        Software='\n'.join(software),
        heartbeat_interval=heartbeat_interval,
    )


def format_tms_xml_response(**format_kwargs):

    default_kwargs = {
        'Configuration': '',
        'Command': '',
        'Calendar': '',
        'DocumentsToPost': '',
        'Software': '',
        'Directory': '',
        'FilesToDownload': '',
        'HeartBeatInterval': format_kwargs.get('heartbeat_interval') or DEFAULT_HEARTBEAT_INTERVAL,
    }

    xml = '''
    <?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
      <soap:Body>
        <PostEventResponse xmlns="http://www.tandberg.net/2004/11/SystemManagementService/">
          <PostEventResult>
            <Management>
             <Directory>{Directory}</Directory>
             <Configuration>{Configuration}</Configuration>
             <Command>{Command}</Command>
             <Calendar>{Calendar}</Calendar>
             <FilesToDownload></FilesToDownload>
             <Software>{Software}</Software>
             <DocumentsToPost>{DocumentsToPost}</DocumentsToPost>
           </Management>
           <HeartBeatInterval>{HeartBeatInterval}</HeartBeatInterval>
         </PostEventResult>
       </PostEventResponse>
     </soap:Body>
   </soap:Envelope>
    '''.strip().format(**{
        **default_kwargs,
        **format_kwargs,
    })

    return xml


@csrf_exempt
def tms_document(request, customer_secret=None, endpoint_secret=None):

    if not request.body:
        return HttpResponse('', status=400)

    if not customer_secret and settings.EPM_EVENT_CUSTOMER_SECRET:
        return HttpResponse('<Forbidden error="missing_customer_key" />', status=403)

    from endpoint.tasks import handle_tms_document as _handle_tms_document

    if settings.ASYNC_CDR_HANDLING and not settings.TEST_MODE:
        _handle_tms_document = _handle_tms_document.delay  # type: ignore

    _handle_tms_document(
        force_text(request.body),
        customer_secret=customer_secret,
        endpoint_secret=endpoint_secret,
        remote_ip=request.META.get('REMOTE_ADDR'),
    )
    return HttpResponse('<OK />')  # status must be 200, otherwise system will be spammed


def handle_tms_document(
    payload: bytes,
    customer_secret: str = None,
    endpoint_secret: str = None,
    remote_ip: Optional[str] = None,
):

    from debuglog.models import EndpointCiscoProvision

    def _log(endpoint=None, content=None, **kwargs):
        try:
            EndpointCiscoProvision.objects.store(
                ip=remote_ip,
                content=payload if content is None else content,
                event='tms_document',
                endpoint=endpoint,
                **kwargs
            )
        except Exception:
            capture_exception()

    if customer_secret:
        customer = Endpoint.objects.get_customer_for_key(customer_secret, raise_exception=False)
    else:
        customer = None

    try:
        event = TMSPostedDocumentEvent(payload, customer=customer, endpoint_secret=endpoint_secret)
        endpoint = event.get_endpoint()
        event.handle_event()
    except (AuthenticationError, Endpoint.DoesNotExist) as e:
        _log(error='Invalid authentication')
        return HttpResponse(str(e), status=403)
    except Exception as e:
        _log(error=format_exception(e))
        return HttpResponse('', status=500)

    prefix = b'<?xml version="1.0"?>\n'

    def _store(key):

        try:
            start = payload.index(b'<' + force_bytes(key.title()))
            stop = payload.rindex(b'</' + force_bytes(key.title()))
            xml = prefix + payload[start : stop + len(key) + 3]
        except (ValueError, IndexError) as e:
            _log(endpoint, 'Store of {} for endpoint {} failed, {}'.format(key, endpoint.pk, e))
            return None, False
        else:
            _log(
                endpoint,
                'Store of {} for endpoint {} succeeded. {} bytes'.format(
                    key, endpoint.pk, len(payload)
                ),
            )
            return EndpointCurrentState.objects.store(endpoint, **{key: xml}), xml

    if b'<Location>/' in payload:  # Dont update for upgrade status events
        endpoint.set_status(ts_last_provision_document=now())

    if b'<Location>/Status</Location>' in payload:
        state, status = _store('status')
        if status:
            parsed = endpoint.get_parser('status', status).parse()
            endpoint.update_status(status_data=parsed)
            endpoint.get_api().check_events_status(status_data=parsed)
    elif b'<Location>/Command</Location>' in payload:
        _store('command')
    elif b'<Location>/Valuespace</Location>' in payload:
        state, valuespace = _store('valuespace')
    elif b'<Location>/Configuration</Location>' in payload:
        state, configuration = _store('configuration')
        if configuration and state.valuespace_id:
            try:
                parsed = endpoint.get_parser('configuration', configuration, valuespace={}).parse()
                endpoint.update_dial_info(configuration_data=parsed)
            except (AuthenticationError, ResponseError):
                pass
            except Exception:
                capture_exception()
    elif b'<UpgradeStatus>' in payload:  # Provision status
        _log(endpoint)
    else:
        _log(endpoint)
        return False

    return True
