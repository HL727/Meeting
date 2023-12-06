import json
from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable

import requests
import xlwt
from django.conf import settings
from django.db import models
from django.utils.timezone import make_naive, now
from django.utils.translation import gettext_lazy as _, ngettext_lazy as _n

from datastore.models import acano as ds
from statistics.models import Leg
from statistics.types import LegSummaryTemp, LegSummaryTempRow, LegSummaryResultRow, LegSummaryResult, LegData
from statistics.utils.leg_collection import LegCollection


def excel_export(legs: LegCollection, summary_data: LegSummaryResult = None, include_cospaces=True, **kwargs):

    leg_data = summary_data or summarize(legs, **kwargs)

    output = xlwt.Workbook()

    def floatformat(s):
        if not isinstance(s, str):
            s = str(s)
        return Decimal(s).quantize(Decimal('.001'))

    context = [None, 0]  # sheet, y-index

    def add_sheet(title):
        sheet = output.add_sheet(title)
        context[0] = sheet
        context[1] = 0
        return sheet

    def add_row(cols):
        x = 0
        for c in cols:
            context[0].write(context[1], x, str(c) if not isinstance(c, (Decimal, datetime, int)) else c)
            x += 1
        context[1] += 1

    if leg_data.cospace and include_cospaces:

        add_sheet(str(_('Per space')))
        add_row(
            [
                str(s)
                for s in [_('Space'), _('Timmar'), _('Gästtimmar'), _('Deltagare'), _('Samtal')]
            ]
        )

        for cospace, data in leg_data.cospace.items():

            add_row([
                cospace,
                floatformat(data.duration),
                floatformat(data.guest_duration),
                data.participant_count,
                data.call_count,
            ])

    def _group(dct):

        add_sheet(str(_('Per grupp')))
        add_row(
            [
                str(s)
                for s in [_('Grupp'), _('Timmar'), _('Gästtimmar'), _('Deltagare'), _('Samtal')]
            ]
        )

        for ou, data in sorted(dct.items()):

            add_row([
                ou,
                floatformat(data.duration),
                floatformat(data.guest_duration),
                data.participant_count,
                data.call_count,
            ])

    if settings.ENABLE_ORGANIZATION:
        _group(leg_data.org_unit)
    elif leg_data.ou:
        _group(leg_data.ou)

    if leg_data.user:

        add_sheet(str(_('Per deltagare')))
        add_row([str(s) for s in [_('Deltagare'), _('Timmar'), _('Gästtimmar'), _('Samtal')]])

        for user, data in leg_data.user.items():

            add_row([
                user,
                floatformat(data.duration),
                floatformat(data.guest_duration),
                data.call_count,
            ])

    (
        target_per_date,
        ou_per_date,
        unit_per_date,
        tenant_per_date,
        total_per_date,
    ) = legs.get_grouped_call_stats_per_day()
    if len(unit_per_date) >= len(ou_per_date):
        per_date = unit_per_date
    else:
        per_date = ou_per_date

    add_sheet(str(_('Per dag, grupp')))
    add_row([str(s) for s in [_('Grupp'), _('Datum'), _('Timmar'), _('Samtal')]])

    for ou in sorted(per_date.keys()):

        for date, stats in per_date[ou].items():
            add_row([
                ou,
                date,
                floatformat(stats[0] / 60 / 60),
                stats[1],
            ])

    add_sheet(str(_('Per dag, deltagare')))
    add_row([str(s) for s in [_('Deltagare'), _('Datum'), _('Timmar'), _('Samtal')]])

    for target in sorted(target_per_date.keys()):

        for date, stats in sorted(target_per_date[target].items()):
            add_row([
                target,
                date,
                floatformat(stats[0] / 60 / 60),
                stats[1],
            ])

    (
        target_per_hour,
        ou_per_hour,
        unit_per_hour,
        tenant_per_hour,
        total_per_hour,
    ) = legs.get_grouped_call_stats_per__hour()
    if len(unit_per_hour) >= len(ou_per_hour):
        per_hour = unit_per_hour
    else:
        per_hour = ou_per_hour

    add_sheet(str(_('Per timme')))
    add_row([str(s) for s in [_('Grupp'), _('Datum'), _('Timmar'), _('Samtal')]])

    for ou in sorted(per_hour.keys()):

        for date, stats in sorted(per_hour[ou].items()):
            add_row([
                ou,
                date,
                floatformat(stats[0] / 60 / 60),
                stats[1],
            ])

    add_sheet(str(_('Per timme, deltagare')))
    add_row([str(s) for s in [_('Deltagare'), _('Datum'), _('Timmar'), _('Samtal')]])

    hour_rows = sum(len(values) for values in target_per_hour.values())

    for target in target_per_hour.keys():
        if hour_rows > 65000:
            add_row(
                [
                    str(
                        _(
                            'Denna vy har inaktiverats av prestandaskäl. Vänligen gör en snävare filtrering eller välj ett mindre tidsområde'
                        )
                    )
                ]
            )
            break

        for hour, stats in sorted(target_per_hour[target].items()):
            add_row([
                target,
                hour,
                floatformat(stats[0] / 60 / 60),
                stats[1],
            ])

    return output


def debug_excel_export(legs: Iterable[LegData], **kwargs):

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active

    ws.append(
        [
            str(s)
            for s in [
                _('Deltagare'),
                _('Lokal part'),
                _('Motstående part'),
                # _('Protokoll'), # TODO LegData must be extended
                _n('Mötesrum', 'Mötesrum', 1),
                _('Starttid'),
                _('Sluttid'),
                _('Sekunder'),
                _('Grupp'),
                _('Organisationsenhet'),
            ]
        ]
    )

    for leg in legs:
        ws.append(
            [
                leg.target,
                leg.local,
                leg.remote,
                # leg.get_protocol_display(),
                leg.call__cospace,
                make_naive(leg.ts_start),
                make_naive(leg.ts_stop),
                leg.duration,
                leg.titles.org_unit,
                leg.titles.ou,
            ]
        )

    for column_cells in ws.columns:
        length = max(len(str(cell.value or '0')) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(60, length)

    return wb


def calculate_stats(usernames, days_back=90):
    if isinstance(usernames, str):
        usernames = [usernames]

    legs = Leg.objects.filter(
        ts_start__gte=now() - timedelta(days=days_back),
        should_count_stats=True,
        target__in=usernames,
    ).order_by().values_list('target').annotate(models.Sum('duration'), models.Count('target'))

    result = {}
    for username, duration, calls in legs:
        result[username] = (calls, duration)

    return result


def send_stats(usernames):

    if not usernames or not getattr(settings, 'SEND_USER_STATS_URLS', None):
        return

    if usernames:
        usernames = ds.User.objects.filter(username__in=usernames).values_list('username', flat=True)

    result = calculate_stats(usernames)

    if not result:
        return result

    for url in settings.SEND_USER_STATS_URLS:
        requests.post(url, json.dumps(result), timeout=120)
    return result


def summarize(legs: LegCollection, ou=None, ts_start=None, ts_stop=None):

    def struct():
        return LegSummaryTempRow(call_counter=set())

    temp = LegSummaryTemp(
        cospace=defaultdict(struct),
        ou=defaultdict(struct),
        user=defaultdict(struct),
        org_unit=defaultdict(struct),
    )

    def _add_call(target: LegSummaryTempRow, leg: LegData, duration: float, related_id=None):

        target.duration += duration
        if leg.is_guest:
            target.guest_duration += duration
        target.participant_count += 1
        target.call_counter.add(leg.call_id)
        if related_id:
            target.related_id = related_id

    related_data = legs.related_data

    for leg, duration in legs.iter_durations(ts_start, ts_stop):

        _add_call(temp.cospace[leg.titles.cospace], leg, duration, leg.call__cospace_id)
        _add_call(temp.user[leg.target], leg, duration, related_data.users.get(leg.target))
        _add_call(temp.ou[leg.titles.ou], leg, duration)
        _add_call(temp.org_unit[leg.titles.org_unit], leg, duration, leg.org_unit)

    result = temp.finalize()

    result.target_group = result.ou
    result.target_group_total = result.ou_total

    if not settings.ENABLE_GROUPS or (len(temp.org_unit) >= len(temp.ou) and not ou):
        if temp.org_unit and list(temp.org_unit) != ['unknown']:
            result.target_group = result.org_unit
            result.target_group_total = result.org_unit_total
    return result
