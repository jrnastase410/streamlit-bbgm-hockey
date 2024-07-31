import plotly.graph_objects as go
import polars as pl
import numpy as np


def player_plot(df, pid):
    plot_df = df.filter(pl.col('pid') == pid)
    player = plot_df.select(pl.first('player')).item()
    title = player

    fig = go.Figure()

    bar_width = 0.4

    # OVERALL
    fig.add_trace(
        go.Scatter(
            x=plot_df['season'],
            y=plot_df['ovr'],
            name='Overall',
            line=dict(
                color='rgb(255, 90, 95)'
            ),
            hovertemplate=
            '<b>Season</b>: %{x}<br>' +
            '<b>Overall</b>: %{y:.1f}<br>'  # Round to 1 decimal place
        )
    )

    # SURPLUS
    fig.add_trace(
        go.Scatter(
            x=plot_df['season'],
            y=plot_df['surplus'],
            name='Surplus',
            line=dict(
                color='rgb(0, 90, 95)'
            ),
            yaxis='y2'
        )
    )

    # VALUE
    fig.add_trace(
        go.Bar(
            x=plot_df['season'] + 0.2,
            y=plot_df['value'],
            name='Value',
            yaxis='y2',
            width=bar_width,
            marker=dict(
                color='rgb(0, 166, 153)'
            ),
            text=[f'${np.round(val, 2)}' for val in list(plot_df['value'])],
            textposition='outside',
            textfont=dict(
                color='rgb(0, 166, 153)',
                size=14,
            ),
        )
    )

    # SALARY
    fig.add_trace(
        go.Bar(
            x=plot_df.filter(pl.col('status') == 'current')['season'] - 0.2,
            y=plot_df.filter(pl.col('status') == 'current')['salary'],
            name='Salary',
            yaxis='y2',
            width=bar_width,
            marker=dict(
                color='rgb(252,100,45)'
            ),
            text=[f'${np.round(val, 2)}' for val in list(plot_df.filter(pl.col('status') == 'current')['salary'])],
            textposition='outside',
            textfont=dict(
                color='rgb(252,100,45)',
                size=14,
            ),
        )
    )

    # Salaries (ProjecteD)
    fig.add_trace(
        go.Bar(
            x=plot_df.filter(pl.col('status') == 'next')['season'] - 0.2,
            y=plot_df.filter(pl.col('status') == 'next')['salary'],
            name='Salary',
            yaxis='y2',
            width=bar_width,
            marker=dict(
                color='rgba(252,100,45,0.5)'
            ),
            text=[f'${np.round(val, 2)}' for val in list(plot_df.filter(pl.col('status') == 'next')['salary'])],
            textposition='outside',
            textfont=dict(
                color='rgb(252,100,45)',
                size=14,
            ),
            showlegend=False,
        )
    )

    # Update the plot title
    fig.update_layout(
        template='simple_white',
        title=title,
        barmode='group',
        yaxis=dict(
            range=[0, 100],
            showgrid=True,
            showticklabels=True,
        ),
        yaxis2=dict(
            range=[0, 50],
            overlaying='y',
            side='right',
            showgrid=False,
            showticklabels=False,
        ),
    )

    return fig
