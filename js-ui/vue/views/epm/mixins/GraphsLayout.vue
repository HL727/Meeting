<script>
const backgroundColor = '#f0f3f7'
const graphColors = {
    green: '#53B27B',
    red: '#E71E18'
}


export default {
    data() {
        return {
            graphColors,
        }
    },
    methods: {
        simplePieChartDefaults() {
            return {
                data: [{
                    type: 'pie',
                    textinfo: 'none',
                    hoverinfo: 'none',
                    values: [],
                    sort: false,
                    direction: 'clockwise',
                    hole: 0.5,
                    marker: {
                        line: {
                            color: 'white',
                            width: 2
                        },
                        colors: [
                            graphColors.green,
                            graphColors.red
                        ]
                    },
                }],
                layout: {
                    width: 100,
                    height: 100,
                    margin: {t: 0, b: 0, l: 0, r: 0},
                    showlegend: false,
                }
            }
        },
        simpleLineChartDefaults() {
            return {
                data: [{}],
                layout: {
                    height: 220,
                    margin: {t: 10, b: 26, l: 10, r: 10},
                    plot_bgcolor: backgroundColor,
                    paper_bgcolor: backgroundColor,
                    xaxis: {
                        autorange: true,
                        zeroline: false,
                        showticklabels: true,
                        //nticks: 8,
                        rangemode: 'tozero',
                        fixedrange: true
                    },
                    yaxis: {
                        autorange: true,
                        zeroline: false,
                        showgrid: false,
                        showticklabels: false,
                        fixedrange: true
                    },
                    showlegend: false
                }
            }
        },
        simpleBarChartDefaults() {
            return {
                data: [{
                    x: [],
                    y: [],
                    mode: 'lines+markers',
                    line: {color: '#1976d2'},
                    type: 'bar'
                }],
                layout: {
                    height: 100,
                    margin: {t: 10, b: 26, l: 10, r: 10},
                    plot_bgcolor: backgroundColor,
                    paper_bgcolor: backgroundColor,
                    xaxis: {
                        autorange: true,
                        zeroline: false,
                        showticklabels: true,
                        rangemode: 'tozero',
                        fixedrange: true
                    },
                    yaxis: {
                        autorange: true,
                        zeroline: false,
                        showgrid: false,
                        showticklabels: false,
                        fixedrange: true
                    },
                    showlegend: false
                }
            }
        }
    }
}
</script>
