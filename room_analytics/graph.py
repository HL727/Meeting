from django.utils.timezone import localtime

from endpoint.consts import DEFAULT_CAPACITY


def get_head_count_graph(endpoints, ts_start, ts_stop, as_percent=False, as_image=False, as_json=False):

    from plotly.graph_objs import Figure, Scatter
    from plotly.graph_objs import scatter
    from room_analytics.utils.report import get_head_count_values

    data = get_head_count_values(endpoints, ts_start, ts_stop, as_percent)

    layout = get_layout(data, as_image=as_image)

    limit_traces = []
    if len(endpoints) == 1 and not as_percent:
        # add first to display at bottom
        limit_traces.append(
            Scatter(
                mode='lines',
                x=[localtime(ts_start), localtime(ts_stop)],
                y=[endpoints[0].room_capacity or DEFAULT_CAPACITY] * 2,
            )
        )

    fig = Figure(
        data=limit_traces
        + [Scatter(x=v.x, y=v.y, name=v.title, line=scatter.Line(shape='hv')) for v in data],
        layout=layout,
    )

    return get_graph(fig, as_image=as_image, as_json=as_json)


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

    layout = Layout(
        **{
        **dict(
            barmode='stack',
            showlegend=extra.pop('showlegend', False),
        ),
        **size,
        **extra,
        }
    )
    return layout


def get_graph(fig, as_image=False, as_json=False):

    fig.update_yaxes(rangemode="tozero")
    if as_image:
        from statistics.graph import to_image
        return to_image(fig)

    if as_json:
        return fig.to_dict()

    return fig.to_html(full_html=False, include_plotlyjs=False)

