from .response import FakeResponse
from .state import State
import json
import re

distinct_ids = {
    'cospace_with_user': 222,
    'cospace_without_user': 123,
    'uri': '65432',

    'leg': '00000000-0000-0000-0000-000000000002',
    'call': '00000000-0000-0000-0000-000000000001',
    'cospace_with_call': 'VMR_1',
}

_objects = {
    'conference': {
        'aliases': [
            {
                'alias': '65432@local.example.org',
                'conference': '/api/admin/configuration/v1/conference/1/',
                'creation_time': '2017-05-11T22:02:05.855877',
                'description': '',
                'id': 1
            },
            {
                'alias': '65432',
                'conference': '/api/admin/configuration/v1/conference/1/',
                'creation_time': '2017-05-11T22:02:05.855877',
                'description': '',
                'id': 2
            },
        ],
        'allow_guests': False,
        "automatic_participants": [
            {
                "alias": "1234@mividas.com",
                "call_type": "video",
                "creation_time": "2020-12-16T16:04:59.514440",
                "description": "",
                "dtmf_sequence": "",
                "id": 1,
                "keep_conference_alive": "keep_conference_alive_if_multiple",
                "presentation_url": "",
                "protocol": "sip",
                "remote_display_name": "",
                "role": "guest",
                "routing": "manual",
                "streaming": False,
            }
        ],
        'call_type': 'video',
        'creation_time': '2017-05-11T22:02:05.848612',
        'crypto_mode': '',
        'description': '',
        'enable_chat': 'default',
        'enable_overlay_text': False,
        'force_presenter_into_main': False,
        'guest_pin': '',
        'guest_view': None,
        'guests_can_present': True,
        'host_view': 'one_main_seven_pips',
        'id': 123,
        'ivr_theme': None,
        'match_string': '',
        'max_callrate_in': None,
        'max_callrate_out': None,
        'max_pixels_per_second': None,
        'mssip_proxy': None,
        'mute_all_guests': False,
        'name': 'VMR_1',
        'participant_limit': None,
        'pin': '',
        'primary_owner_email_address': '',
        'replace_string': '',
        'resource_uri': '/api/admin/configuration/v1/conference/123/',
        'service_type': 'conference',
        'sync_tag': '',
        'system_location': None,
        'tag': ''
    },
    'conferencealias':  {
        "alias": "65432@local.example.org",
        "conference": "/api/admin/configuration/v1/conference/123/",
        "creation_time": "2019-12-06T11:37:09.582041",
        "description": "Default alias",
        "id": 1,
        "resource_uri": "/api/admin/configuration/v1/conference_alias/1/"
    },
    'end_user':   {
        "avatar_url": "",
        "department": "",
        "description": "Test",
        "display_name": "",
        "first_name": "",
        "id": 1,
        "last_name": "",
        "mobile_number": "",
        "ms_exchange_guid": None,
        "primary_email_address": "test@example.org",
        "resource_uri": "/api/admin/configuration/v1/end_user/1/",
        "sync_tag": "",
        "telephone_number": "",
        "title": "",
        "uuid": "c35571e7-d5e1-402f-b4ee-a46dada709d7"
    },
        'gateway_routing_rule': json.loads('''{
  "call_type": "video",
  "called_device_type": "external",
  "creation_time": "2020-08-20T13:55:45.151878",
  "crypto_mode": "",
  "description": "Bit longer description text here",
  "enable": true,
  "external_participant_avatar_lookup": "default",
  "gms_access_token": null,
  "h323_gatekeeper": null,
  "id": 1,
  "ivr_theme": null,
  "match_incoming_calls": true,
  "match_incoming_h323": true,
  "match_incoming_mssip": true,
  "match_incoming_only_if_registered": false,
  "match_incoming_sip": true,
  "match_incoming_webrtc": true,
  "match_outgoing_calls": false,
  "match_source_location": null,
  "match_string": "^abc",
  "match_string_full": false,
  "max_callrate_in": null,
  "max_callrate_out": null,
  "max_pixels_per_second": null,
  "mssip_proxy": null,
  "name": "Outgoing calls for a customer",
  "outgoing_location": null,
  "outgoing_protocol": "teams",
  "priority": 2,
  "replace_string": "",
  "resource_uri": "/api/admin/configuration/v1/gateway_routing_rule/1/",
  "sip_proxy": null,
  "stun_server": null,
  "tag": "",
  "teams_proxy": "/api/admin/configuration/v1/teams_proxy/1/",
  "treat_as_trusted": false,
  "turn_server": null
}'''),
     'history_conference':    {
      "duration": 3278,
      "end_time": "2020-12-21T08:59:31.112339",
      "id": "c4cc1c92-6b05-4ed9-9be6-92074cfecf7f",
      "instant_message_count": 0,
      "name": "Meetup",
      "participant_count": 2,
      "participants": [
        "/api/admin/history/v1/participant/a94332fc-7a07-4935-9f78-6f87bc4df0d0/",
        "/api/admin/history/v1/participant/f898bff0-06c7-4440-894b-374948e0aaf4/"
      ],
      "resource_uri": "/api/admin/history/v1/conference/c4cc1c92-6b05-4ed9-9be6-92074cfecf7f/",
      "service_type": "conference",
      "start_time": "2020-12-21T08:04:52.307927",
      "tag": ""
    },
    'history_participant': {
        "av_id": "97cbab1c-21b7-4a2d-8236-b8517a5e39dd",
        "bandwidth": 448,
        "bucketed_call_quality": [
            0,
            58,
            0,
            0,
            0
        ],
        "call_direction": "in",
        "call_quality": "1_good",
        "call_tag": "",
        "call_uuid": "a94332fc-7a07-4935-9f78-6f87bc4df0d0",
        "conference": "/api/admin/history/v1/conference/c4cc1c92-6b05-4ed9-9be6-92074cfecf7f/",
        "conference_name": "Meetup",
        "conversation_id": "a94332fc-7a07-4935-9f78-6f87bc4df0d0",
        "disconnect_reason": "Call disconnected",
        "display_name": "Anders",
        "duration": 1178,
        "encryption": "On",
        "end_time": "2020-12-21T08:59:29.878137",
        "has_media": True,
        "historic_call_quality": [
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1
        ],
        "id": "a94332fc-7a07-4935-9f78-6f87bc4df0d0",
        "is_streaming": False,
        "license_count": 1,
        "license_type": "port",
        "local_alias": "meetup",
        "media_node": "10.1.2.3",
        "media_streams": [
            {
                "end_time": "2020-12-21T08:59:29.279279",
                "id": 279,
                "node": "10.1.2.3",
                "participant": "/api/admin/history/v1/participant/a94332fc-7a07-4935-9f78-6f87bc4df0d0/",
                "rx_bitrate": 34,
                "rx_codec": "opus",
                "rx_fps": 0.0,
                "rx_packet_loss": 0.0,
                "rx_packets_lost": 0,
                "rx_packets_received": 58823,
                "rx_resolution": "",
                "start_time": "2020-12-21T08:39:51.667494",
                "stream_id": "0",
                "stream_type": "audio",
                "tx_bitrate": 78,
                "tx_codec": "opus",
                "tx_fps": 0.0,
                "tx_packet_loss": 0.0,
                "tx_packets_lost": 2,
                "tx_packets_sent": 58862,
                "tx_resolution": ""
            },
            {
                "end_time": "2020-12-21T08:59:29.280748",
                "id": 280,
                "node": "10.1.2.3",
                "participant": "/api/admin/history/v1/participant/a94332fc-7a07-4935-9f78-6f87bc4df0d0/",
                "rx_bitrate": 388,
                "rx_codec": "VP9",
                "rx_fps": 31.5,
                "rx_packet_loss": 0.0,
                "rx_packets_lost": 0,
                "rx_packets_received": 66813,
                "rx_resolution": "1280x720",
                "start_time": "2020-12-21T08:39:51.760685",
                "stream_id": "1",
                "stream_type": "video",
                "tx_bitrate": 402,
                "tx_codec": "VP9",
                "tx_fps": 25.0,
                "tx_packet_loss": 0.02,
                "tx_packets_lost": 12,
                "tx_packets_sent": 61843,
                "tx_resolution": "1024x576"
            }
        ],
        "parent_id": "",
        "presentation_id": "",
        "protocol": "WebRTC",
        "proxy_node": "10.66.6.17",
        "remote_address": "185.32.10.83",
        "remote_alias": "Test",
        "remote_port": 62558,
        "resource_uri": "/api/admin/history/v1/participant/a94332fc-7a07-4935-9f78-6f87bc4df0d0/",
        "role": "chair",
        "rx_bandwidth": 1722,
        "service_tag": "",
        "service_type": "conference",
        "signalling_node": "10.1.2.4",
        "start_time": "2020-12-21T08:39:50.905201",
        "system_location": "Prod",
        "tx_bandwidth": 448,
        "vendor": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
    },
    'status_participant': {
        'bandwidth': 576,
        'call_direction': 'in',
        'call_quality': '1_good',
        'call_uuid': '1c26be9c-6511-4e5c-9588-8351f8c3decd',
        'conference': 'VMR_1',
        'connect_time': '2015-04-02T09:46:11.116767',
        'conversation_id': '1c26be9c-6511-4e5c-9588-8351f8c3decd',
        'destination_alias': '65432@local.example.org',
        'display_name': 'Alice',
        'encryption': 'On',
        'has_media': False,
        'id': '00000000-0000-0000-0000-000000000002',
        'is_disconnect_supported': True,
        'is_mute_supported': True,
        'is_muted': False,
        'is_on_hold': False,
        'is_presentation_supported': True,
        'is_presenting': False,
        'is_streaming': False,
        'is_transfer_supported': True,
        'license_count': 0,
        'license_type': 'nolicense',
        'media_node': '10.0.0.1',
        'parent_id': '',
        'participant_alias': '445522@remote.example.org',
        'protocol': 'WebRTC',
        'proxy_node': '10.10.0.46',
        'remote_address': '10.0.0.3',
        'remote_port': 54686,
        'resource_uri': '/api/admin/status/v1/participant/00000000-0000-0000-0000-000000000002/',
        'role': 'chair',
        'service_tag': '',
        'service_type': 'conference',
        'signalling_node': '10.0.0.1',
        'source_alias': '445566@remote.example.org',
        'system_location': 'London',
        'vendor': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.101 Safari/537.36'
    }
}

eventsink_events = {
    'conference_started': json.loads('''{
            "data": {
                "guests_muted": false,
                "is_locked": false,
                "is_started": false,
                "name": "meet.webapp",
                "service_type": "conference",
                "start_time": 1559897886.582629,
                "tag": ""
            },
            "event": "conference_started",
            "node": "10.47.2.21",
            "seq": 2,
            "time": 1559897886.582629,
            "version": 1
}'''),
    'conference_ended': json.loads('''{
            "data": {
                "guests_muted": false,
                "is_locked": false,
                "is_started": false,
                "name": "meet.webapp",
                "service_type": "conference",
                "start_time": 1559897886.582629,
                "end_time": 1559898886.582629,
                "tag": ""
            },
            "event": "conference_ended",
            "node": "10.47.2.21",
            "seq": 2,
            "time": 1559898886.582629,
            "version": 1
}'''),
    'participant_disconnected': json.loads('''{
	"data": {
		"call_direction": "in",
		"call_id": "ac58a572-33e5-4b19-ac1c-f0b1d22215e6",
		"conference": "meet.webapp",
		"connect_time": 1559897886.593371,
		"service_tag": "",
		"conversation_id": "ac58a572-33e5-4b19-ac1c-f0b1d22215e6",
		"destination_alias": "meet.webapp",
		"disconnect_reason": "Call disconnected",
		"display_name": "Alice",
		"has_media": false,
		"is_muted": false,
		"is_presenting": false,
		"is_streaming": false,
		"media_node": "10.47.2.21",
		"media_streams": [
			{
			"end_time": 1559898886.767812,
			"node": "10.47.2.21",
			"rx_bitrate": 32,
			"rx_codec": "opus",
			"rx_packet_loss": 0.0,
			"rx_packets_lost": 0,
			"rx_packets_received": 1977,
			"rx_resolution": "",
			"start_time": 1559902904.1698,
			"stream_id": 0,
			"stream_type": "audio",
			"tx_bitrate": 1,
			"tx_codec": "opus",
			"tx_packet_loss": 0.0,
			"tx_packets_lost": 0,
			"tx_packets_sent": 2020,
			"tx_resolution": ""
			},
			{
			"end_time": 1559898886.768668,
			"node": "10.47.2.21",
			"rx_bitrate": 1405,
			"rx_codec": "VP8",
			"rx_packet_loss": 0.0,
			"rx_packets_lost": 0,
			"rx_packets_received": 4493,
			"rx_resolution": "1280x720",
			"start_time": 1559902904.318265,
			"stream_id": 1,
			"stream_type": "video",
			"tx_bitrate": 1545,
			"tx_codec": "VP8",
			"tx_packet_loss": 0.0,
			"tx_packets_lost": 0,
			"tx_packets_sent": 6883,
			"tx_resolution": "1280x720"
			}
		],	"protocol": "WebRTC",
		"remote_address": "10.47.2.200",
		"role": "chair",
		"service_type": "conference",
		"signalling_node": "10.47.2.21",
		"source_alias": "Alice",
		"system_location": "Oslo",
		"uuid": "ac58a572-33e5-4b19-ac1c-f0b1d22215e6",
		"vendor": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.110 Safari/537.36"
	},
	"event": "participant_disconnected",
	"node": "10.47.2.21",
	"seq": 4,
	"time": 1559898886.526124,
	"version": 1
}'''),
    'participant_connected': json.loads('''{
	"data": {
		"call_direction": "in",
		"call_id": "ac58a572-33e5-4b19-ac1c-f0b1d22215e6",
		"conference": "meet.webapp",
		"connect_time": 1559897886.593371,
		"service_tag": "",
		"conversation_id": "ac58a572-33e5-4b19-ac1c-f0b1d22215e6",
		"destination_alias": "meet.webapp",
		"disconnect_reason": "Call disconnected",
		"display_name": "Alice",
		"has_media": false,
		"is_muted": false,
		"is_presenting": false,
		"is_streaming": false,
		"media_node": "10.47.2.21",
		"protocol": "WebRTC",
		"remote_address": "10.47.2.200",
		"role": "chair",
		"service_type": "conference",
		"signalling_node": "10.47.2.21",
		"source_alias": "Alice",
		"system_location": "Oslo",
		"uuid": "ac58a572-33e5-4b19-ac1c-f0b1d22215e6",
		"vendor": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.110 Safari/537.36"
	},
	"event": "participant_connected",
	"node": "10.47.2.21",
	"seq": 4,
	"time": 1559897886.526124,
	"version": 1
}'''),



}

pexip_requests = {
    'POST configuration/v1/': (201, {'Location': '/admin/api/configuration/v1/conference/123/'}),
    'GET configuration/v1/conference/': State({
        'initial': {
            "meta": {
                "limit": 20,
                "next": None,
                "offset": 0,
                "previous": None,
                "total_count": 7
            },
            'objects': [
                _objects['conference'],
                {**_objects['conference'], 'id': 222, 'primary_owner_email_address': 'test@example.org'},
            ],
        },
        '404conf': (404, {}),
    }),
    'GET configuration/v1/conference/123/': _objects['conference'],
    'GET configuration/v1/conference/222/': {**_objects['conference'], 'id': 222, 'primary_owner_email_address': 'test@example.org'},
    'PUT configuration/v1/conference/123/': (204, _objects['conference']),
    'PATCH configuration/v1/conference/123/': (202, _objects['conference']),
    'PATCH configuration/v1/conference/222/': (202, _objects['conference']),
    'GET configuration/v1/conference_alias/': {
        "meta": {
            "limit": 20,
            "next": None,
            "offset": 0,
            "previous": None,
            "total_count": 6
        },
        "objects": [
            _objects['conferencealias'],
        ]
    },
    'PATCH configuration/v1/conference_alias/1/': (202, _objects['conferencealias']),
    'PUT configuration/v1/conference_alias/1/': (204, _objects['conferencealias']),
    'DELETE configuration/v1/conference_alias/1/': (204, ''),
    'DELETE configuration/v1/conference_alias/2/': (204, ''),
    'POST configuration/v1/conference_alias/': (201, {'Location': '/admin/api/configuration/v1/conference_alias/1/'}),
    'GET history/v1/conference/': {
        "meta": {
            "limit": 20,
            "next": None,
            "offset": 0,
            "previous": None,
            "total_count": 6
        },
        "objects": [
            _objects['history_conference'],
        ]
    },
    'GET history/v1/participant/': {
        "meta": {
            "limit": 20,
            "next": None,
            "offset": 0,
            "previous": None,
            "total_count": 6
        },
        "objects": [
            _objects['history_participant'],
        ]
    },
    'GET status/v1/conference/': {
        'meta': {'total_count': 1},
        'objects': [
            {
                'start_time': '2015-04-02T09:46:06.106482',
                'resource_uri': '/api/admin/status/v1/conference/00000000-0000-0000-0000-000000000001/',
                'id': '00000000-0000-0000-0000-000000000001',
                'name': 'VMR_1',
                'service_type': 'conference',
                'is_locked': False,
                'is_started': True,
                'guests_muted': False,
                'tag': ''
            },
        ],
    },
    'GET status/v1/conference/00000000-0000-0000-0000-000000000001/': {
        'start_time': '2015-04-02T09:46:06.106482',
        'resource_uri': '/api/admin/status/v1/conference/00000000-0000-0000-0000-000000000001/',
        'id': '00000000-0000-0000-0000-000000000001',
        'name': 'VMR_1',
        'service_type': 'conference',
        'is_locked': False,
        'is_started': True,
        'guests_muted': False,
        'tag': ''
    },
    'GET status/v1/participant/': {
        'meta': {'total_count': 1},
        'objects': [
            _objects['status_participant'],
        ],
    },
    'GET status/v1/participant/00000000-0000-0000-0000-000000000002/': {
        'bandwidth': 576,
        'call_direction': 'in',
        'call_quality': '1_good',
        'call_uuid': '1c26be9c-6511-4e5c-9588-8351f8c3decd',
        'conference': 'VMR_1',
        'connect_time': '2015-04-02T09:46:11.116767',
        'conversation_id': '1c26be9c-6511-4e5c-9588-8351f8c3decd',
        'destination_alias': '65432@local.example.org',
        'display_name': 'Alice',
        'encryption': 'On',
        'has_media': False,
        'id': '00000000-0000-0000-0000-000000000002',
        'is_disconnect_supported': True,
        'is_mute_supported': True,
        'is_muted': False,
        'is_on_hold': False,
        'is_presentation_supported': True,
        'is_presenting': False,
        'is_streaming': False,
        'is_transfer_supported': True,
        'license_count': 0,
        'license_type': 'nolicense',
        'media_node': '10.0.0.1',
        'parent_id': '',
        'participant_alias': '445566@remote.example.org',
        'protocol': 'WebRTC',
        'proxy_node': '10.10.0.46',
        'remote_address': '10.0.0.3',
        'remote_port': 54686,
        'resource_uri': '/api/admin/status/v1/participant/00000000-0000-0000-0000-000000000002/',
        'role': 'chair',
        'service_tag': '',
        'service_type': 'conference',
        'signalling_node': '10.0.0.1',
        'source_alias': '445566@remote.example.org',
        'system_location': 'London',
        'vendor': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.101 Safari/537.36'
    },
    'GET configuration/v1/device/': {
        "meta": {"limit": 20, "next": None, "offset": 0, "previous": None, "total_count": 0},
        "objects": [],
    },
    'GET configuration/v1/device/?alias=sip@example.org': {
        "meta": {"limit": 20, "next": None, "offset": 0, "previous": None, "total_count": 1},
        "objects": [
            {
                "alias": "sip@example.org",
                "creation_time": "2020-11-16T15:46:32.339239",
                "description": "Test",
                "enable_h323": False,
                "enable_infinity_connect_non_sso": False,
                "enable_infinity_connect_sso": False,
                "enable_sip": True,
                "id": 1,
                "password": "sdfgsdfg",
                "primary_owner_email_address": "",
                "resource_uri": "/api/admin/configuration/v1/device/1/",
                "sync_tag": "",
                "tag": "",
                "username": "mividas",
            },
        ],
    },
    'POST configuration/v1/device/': (201, {'Location': '/api/admin/configuration/v1/device/1/'}),
    'GET configuration/v1/end_user/': {
        "meta": {
            "limit": 20,
            "next": None,
            "offset": 0,
            "previous": None,
            "total_count": 7
        },
        'objects': [
            _objects['end_user'],
            {
                **_objects['end_user'],
                'id': 333,
                'primary_email_address': 'user2@example.org',
            },
        ],
    },
    'GET status/v1/worker_vm/': {
        "meta": {
            "limit": 20,
            "next": None,
            "offset": 0,
            "previous": None,
            "total_count": 1
        },
        "objects": [
            {
                "boot_time": "2020-11-27T20:40:44.605738",
                "configuration_id": 2,
                "cpu_capabilities": "AVX2",
                "cpu_count": 4,
                "cpu_model": "AMD Ryzen 9 3900 12-Core Processor",
                "deploy_error": "",
                "deploy_progress": 100,
                "deploy_status": "deploy_succeeded",
                "hypervisor": "QEMU",
                "id": 2,
                "last_reported": "2021-03-12T14:47:45",
                "last_updated": "2021-03-11T13:22:44",
                "maintenance_mode": False,
                "max_audio_calls": 172,
                "max_full_hd_calls": 5,
                "max_hd_calls": 9,
                "max_media_tokens": 172,
                "max_sd_calls": 22,
                "media_load": 0,
                "media_tokens_used": 0,
                "name": "pexipc1",
                "node_type": "CONFERENCING",
                "resource_uri": "/api/admin/status/v1/worker_vm/2/",
                "signaling_count": 0,
                "system_location": "Test",
                "total_ram": 3097356,
                "upgrade_status": "IDLE",
                "version": "24 (55691.0.0)"
            }
        ]
    },
    'GET configuration/v1/end_user/333/': _objects['end_user'],
    'GET configuration/v1/end_user/1/': {
        **_objects['end_user'],
        'id': 333,
        'primary_email_address': 'user2@example.org',
    },
    'GET configuration/v1/gateway_routing_rule/': {
        "meta": {
            "limit": 20,
            "next": None,
            "offset": 0,
            "previous": None,
            "total_count": 7
        },
        'objects': [
            _objects['gateway_routing_rule'],
        ],
    },
    'GET configuration/v1/gateway_routing_rule/1/': _objects['gateway_routing_rule'],
    'PATCH configuration/v1/gateway_routing_rule/1/': (204, _objects['gateway_routing_rule']),
    'DELETE configuration/v1/gateway_routing_rule/1/': (204, {}),
    'POST configuration/v1/gateway_routing_rule/': (201, {'Location': '/api/admin/configuration/v1/gateway_routing_rule/1/'}),
    'POST configuration/v1/event_sink/': (201, {'Location': '/api/admin/configuration/v1/event_sink/1/'}),
    'POST configuration/v1/policy_server/': (201, {'Location': '/api/admin/configuration/v1/policy_server/1/'}),
    'POST command/v1/participant/dial/': (202, {'data': {'participant_id': '00000000-0000-0000-0000-000000000002', 'participant_ids': ['00000000-0000-0000-0000-000000000002']}, 'status': 'success'}),
    'POST command/v1/participant/disconnect//': {},
    'GET configuration/v1/system_location/': {
        'meta': {'limit': 9999, 'next': None, 'offset': 0, 'previous': None, 'total_count': 1}, 'objects': [
            {'bdpm_pin_checks_enabled': 'GLOBAL', 'bdpm_scan_quarantine_enabled': 'GLOBAL',
             'client_stun_servers': [], 'description': '', 'dns_servers': [], 'event_sinks': [],
             'h323_gatekeeper': None, 'http_proxy': None, 'id': 1, 'local_mssip_domain': '', 'media_qos': 0,
             'mssip_proxy': None, 'mtu': 1500, 'name': 'Test', 'ntp_servers': [], 'overflow_location1': None,
             'overflow_location2': None, 'policy_server': '/api/admin/configuration/v1/policy_server/1/',
             'resource_uri': '/api/admin/configuration/v1/system_location/1/', 'signalling_qos': 0,
             'sip_proxy': None, 'snmp_network_management_system': None, 'stun_server': None,
             'teams_proxy': None, 'transcoding_location': None, 'turn_server': None}]},
    'GET configuration/v1/sip_proxy/?limit=9999': {
        'meta': {'limit': 9999, 'next': None, 'offset': 0, 'previous': None, 'total_count': 1}, 'objects': [
            {'address': 'test.com', 'description': '', 'id': 1, 'name': 'sip.proxy.test', 'port': 5061,
             'resource_uri': '/api/admin/configuration/v1/sip_proxy/1/', 'transport': 'tls'}]},
    'GET configuration/v1/teams_proxy/?limit=9999': {
        'meta': {'limit': 9999, 'next': None, 'offset': 0, 'previous': None, 'total_count': 1}, 'objects': [
            {'address': 'test.com', 'azure_tenant': '/api/admin/configuration/v1/azure_tenant/1/',
             'description': '', 'id': 1, 'name': 'test', 'port': 443,
             'resource_uri': '/api/admin/configuration/v1/teams_proxy/1/'}]},
    'GET configuration/v1/gms_access_token/?limit=9999': {
        'meta': {'limit': 9999, 'next': None, 'offset': 0, 'previous': None, 'total_count': 1}, 'objects': [
            {'id': 1, 'name': 'google test',
             'resource_uri': '/api/admin/configuration/v1/gms_access_token/1/',
             'token': '$~!1AnMac4Qd1f4AAyyQqa4KZmwTERS/XbnemyEJRV/IF/wl/U+xzZuJNla/jDKV2GkmL3ftuuUMZSg0ilcXVtppS5l/KmazsYegvfsR3qJMQGXrZ5Flt79968KQknihtJsAOSPqeJHFG9ZY5fSANj3jTjjzQKjDMDGjDH+mrDL4juCCJmWzVQi/n7kO4cE5NZYX'}]},
    'GET configuration/v1/h323_gatekeeper/?limit=9999': {
        'meta': {'limit': 9999, 'next': None, 'offset': 0, 'previous': None, 'total_count': 1}, 'objects': [
            {'address': 'h323.test.com', 'description': '', 'id': 1, 'name': 'h323.test.com', 'port': 1719,
             'resource_uri': '/api/admin/configuration/v1/h323_gatekeeper/1/'}]},
    'GET configuration/v1/mssip_proxy/?limit=9999': {
        'meta': {'limit': 9999, 'next': None, 'offset': 0, 'previous': None, 'total_count': 1}, 'objects': [
            {'address': 'mssip.test.com', 'description': '', 'id': 1, 'name': 'msstip.test.com', 'port': 5061,
             'resource_uri': '/api/admin/configuration/v1/mssip_proxy/1/', 'transport': 'tls'}]},
    'GET configuration/v1/stun_server/?limit=9999': {
        'meta': {'limit': 9999, 'next': None, 'offset': 0, 'previous': None, 'total_count': 1}, 'objects': [
            {'address': 'stun.l.google.com', 'description': '', 'id': 1, 'name': 'stun.l.google.com',
             'port': 19302, 'resource_uri': '/api/admin/configuration/v1/stun_server/1/'}]},
    'GET configuration/v1/turn_server/?limit=9999': {
        'meta': {'limit': 9999, 'next': None, 'offset': 0, 'previous': None, 'total_count': 1}, 'objects': [
            {'address': 'turn.test.com', 'description': '', 'id': 1, 'name': 'turn.test.com',
             'password': '$~!1plXrGLW/+NSe9rF0wbA54gpa409EbzpBKb7sUuqByloVdoVXleVEDdtLFO8I3HPWtKRIiBS8TwmFVZ9YJgty1gYtzaCfitnh2mIz0hkmCz6po3Ns12FJehehU/Zvi//Sh8nyEOi/jU/TXZrJpXzJyTh1Y0YdYGk6p+8ZZ4J3oR9oPYcI9WULOzOx/EWwr9Db',
             'port': 3478, 'resource_uri': '/api/admin/configuration/v1/turn_server/1/', 'username': ''}]},
    'GET configuration/v1/ivr_theme/': {
        'meta': {'limit': 9999, 'next': None, 'offset': 0, 'previous': None, 'total_count': 4}, 'objects': [
            {'id': 2, 'last_updated': '2020-07-17T18:12:34.592223', 'name': 'Pexip theme (English_UK)',
             'resource_uri': '/api/admin/configuration/v1/ivr_theme/2/', 'uuid': 'defaultplushash'},
            {'id': 3, 'last_updated': '2020-07-17T18:12:34.592223',
             'name': 'Pexip theme (English_UK) with entry tones',
             'resource_uri': '/api/admin/configuration/v1/ivr_theme/3/', 'uuid': 'defaultplushashtones'},
            {'id': 4, 'last_updated': '2020-07-17T18:12:34.592223', 'name': 'Pexip theme (English_US)',
             'resource_uri': '/api/admin/configuration/v1/ivr_theme/4/', 'uuid': 'defaultnotones'},
            {'id': 1, 'last_updated': '2020-07-17T18:12:34.592223',
             'name': 'Pexip theme (English_US) with entry tones',
             'resource_uri': '/api/admin/configuration/v1/ivr_theme/1/', 'uuid': 'defaultplustones'}]},
    'GET configuration/v1/automatic_participant/': {
        "meta": {
            "limit": 20,
            "next": None,
            "offset": 0,
            "previous": None,
            "total_count": 1
        },
        "objects": [
            {
                "alias": "1234@mividas.com",
                "call_type": "video",
                "conference": [
                    "/api/admin/configuration/v1/conference/6/"
                ],
                "creation_time": "2020-12-16T16:04:59.514440",
                "description": "",
                "dtmf_sequence": "",
                "id": 1,
                "keep_conference_alive": "keep_conference_alive_if_multiple",
                "presentation_url": "",
                "protocol": "sip",
                "remote_display_name": "",
                "resource_uri": "/api/admin/configuration/v1/automatic_participant/1/",
                "role": "guest",
                "routing": "manual",
                "streaming": False,
                "system_location": None,
            }
        ]
    },
    'POST command/v1/conference/sync/': {},
}


def pexip_post(self, url, *args, **kwargs):
    from . import state
    method = kwargs.pop('method', '') or 'POST'

    url = url.replace('/admin/api/', '')

    def ret(response, url):
        if isinstance(response, State):
            response = response.get(state.url_state) or response.get('initial')
        if isinstance(response, tuple):
            return FakeResponse(response[1], status_code=response[0], url=url)
        else:
            return FakeResponse(response, url=url)

    def _match(url):
        for call, response in sorted(iter(list(pexip_requests.items())), key=lambda x: -len(x[0])):

            if call in '%s %s' % (method, url):
                return ret(response, url)

    m = _match(url)
    if not m:
        m = _match(re.sub(r'\?.*', '', url))  # try without query
    if m:
        return m
    return FakeResponse({"status": "error", "method": method, "url": url}, url=url, status_code=404)
