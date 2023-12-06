import os
from typing import Sequence

from cacheout import memoize
from django.conf import settings
from django.utils.timezone import localtime

from .utils.leg_collection import populate_legs, LegCollection
from .utils.time import TimeRangeChunker
from .types import TimeSpanStartDurationTuple
import requests
import json


def to_image(fig):
    import plotly.utils
    import plotly.io as pio
    try:
        import kaleido
    except ImportError:
        kaleido = False

    if not kaleido and '://' in settings.ORCA and not settings.TEST_MODE:
        json_data = json.dumps({
            'figure': fig.to_dict(),
            'format': 'png',
            'scale': '1',
            'width': fig.layout.width,
            'height': fig.layout.height,
            }, cls=plotly.utils.PlotlyJSONEncoder)
        return requests.post(settings.ORCA, json_data).content

    if not kaleido:
        pio.orca.config.executable = settings.ORCA
    return pio.to_image(fig, format='png')


def chunk_duration_between(
    start, stop, hours=1, group_dateformat=None, convert_localtime=True
) -> Sequence[TimeSpanStartDurationTuple]:

    if convert_localtime:
        start, stop = localtime(start), localtime(stop)

    if not group_dateformat and hours % 24 == 0:
        format = '%Y-%m-%d'
    else:
        format = group_dateformat or '%Y-%m-%d %H:00'

    chunker = TimeRangeChunker(resolution_seconds=hours * 60 * 60)
    return list(chunker.iter_chunks_duration(start, stop, group_dateformat=format))


class CallStatisticsGraph:
    def __init__(self, leg_collection: LegCollection):
        self.leg_collection = leg_collection

    def _get_value(self, grouped_data, total=False):
        """
        Select one of the deprecated standard group values
        """
        target_data, ou_data, unit_data, total_data = grouped_data
        if total:
            return total_data
        elif len(unit_data) > len(ou_data) or not settings.ENABLE_GROUPS:
            return unit_data
        return ou_data


class CallSecondsLineGraph(CallStatisticsGraph):

    def get_graph_by_day(self, total=False, as_image=False, as_json=False):
        grouped_data = self.leg_collection.get_grouped_call_seconds_per_day()
        return self.get_value_graph(grouped_data, total=total, as_image=as_image, as_json=as_json)

    def get_graph_by_hour(self, total=False, as_image=False, as_json=False):
        grouped_data = self.leg_collection.get_grouped_call_seconds_per__hour()
        return self.get_value_graph(grouped_data, total=total, as_image=as_image, as_json=as_json)

    def get_graph_by_time_of_day(self, total=False, as_image=False, as_json=False):
        grouped_data = self.leg_collection.get_grouped_call_seconds_per_time_of_day()
        return self.get_value_graph(grouped_data, total=total, as_image=as_image, as_json=as_json)

    def get_value_graph(self, grouped_data, total=False, as_image=False, as_json=False):
        return self.get_graph(self._get_value(grouped_data, total=total), as_image=as_image, as_json=as_json)

    def get_graph(self, data, as_image=False, as_json=False):

        lines = []
        for ou in sorted(data.keys(), reverse=True):
            items = sorted(data[ou].items())
            cur = {
                'x': [i[0] for i in items],
                'y': [round((i[1] * 2) / (60 * 60.0)) / 2 for i in items],
                'name': ou,
                'type': 'bar',
            }
            lines.append(cur)

        if not lines:
            return ''

        fig = None
        layout = get_layout(lines, as_image=as_image)

        if not as_json or (settings.DEBUG or settings.TEST_MODE):
            from plotly.graph_objs import Figure
            fig = Figure(data=lines, layout=layout)  # validation is slow

        if as_json:
            return {'data': lines, 'layout': {**get_plotly_template_json(), **layout._props}}

        if as_image:
            return to_image(fig)

        return fig.to_html(full_html=False, include_plotlyjs=False)


def get_graph(legs, related_data=None, by='day', as_image=False, ts_start=None, ts_stop=None, total=False, as_json=False):
    """
    Deprecated. Replace with ``CallSecondsLineGraph.get_graph_by_<x>``
    """
    graph = CallSecondsLineGraph(LegCollection.from_legs(legs, related_data))
    if by == 'day':
        return graph.get_graph_by_day(total=total, as_image=as_image, as_json=as_json)
    elif by == 'hour':
        return graph.get_graph_by_hour(total=total, as_image=as_image, as_json=as_json)
    elif by == 'time_of_day':
        return graph.get_graph_by_time_of_day(total=total, as_image=as_image, as_json=as_json)
    else:
        raise KeyError('{} not valid timespan'.format(by))


def get_sametime_graph(legs: LegCollection, resolution=None, bars=600, as_image=False, as_json=False):

    if not legs:
        return ''

    if resolution is None:
        resolution = 10
        ts = sorted(l.ts_start for l in legs if l.ts_start)
        if len(ts):
            resolution = min(20, (((ts[-1] - ts[0]).days + 1) * 24 * 60) // bars)

    data, unit_data, tenant_data, total_data = legs.grouped_legs_count_for_chunks(resolution_seconds=resolution * 60)

    if len(unit_data) > len(data) or not settings.ENABLE_GROUPS:
        data = unit_data

    lines = []
    for ou in sorted(data.keys(), reverse=True):
        target = data[ou]
        keys = list(target.keys())
        cur = {
            'x': keys,
            'y': [target[key] for key in keys],
            'name': ou,
            'type': 'bar',
            'width': resolution * 60 * 1000,
        }
        lines.append(cur)

    if not lines:
        return ''

    layout = get_layout(lines, as_image=as_image)
    fig = None

    if not as_json or (settings.DEBUG or settings.TEST_MODE):
        from plotly.graph_objs import Figure
        fig = Figure(data=lines, layout=layout)  # validation is slow

    if as_json:
        return {'data': lines, 'layout': {**get_plotly_template_json(), **layout._props}}

    if as_image:
        return to_image(fig)

    return fig.to_html(full_html=False, include_plotlyjs=False)


def get_layout(data, as_image=False, **extra):

    from plotly.graph_objs import Layout
    from plotly.graph_objs.layout import Margin

    size = dict(
         margin=Margin(
            l=30,
            r=20,
            b=30,
            t=30,
            pad=4
        ),
    )
    if as_image:
        size.update(dict(
            autosize=False,
            width=1024,
            height=576,
        ))

    is_dict = data and isinstance(data[0], dict)

    return Layout(
        **{
            **dict(
                barmode='stack',
                showlegend=len(data) > 1 and (len(data) < 5 or not any(len(l.name if not is_dict else l['name']) > 30 for l in data)),
            ),
            **extra,
            **size
        }
    )


@memoize(1)
def get_plotly_template_json():
    """
    plotly is really slow to use and import, and eats lots of memory.
    it should be changed to plain objects everywhere
    """
    cached_filename = os.path.join(settings.BASE_DIR, 'statistics/plotly_layout.json')
    if os.path.exists(cached_filename):
        with open(cached_filename) as fd:
            data = json.loads(fd.read())
        if data:
            return data

    from plotly.io import templates
    return templates['plotly'].to_plotly_json()['layout']
