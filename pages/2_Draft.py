import streamlit as st
import polars as pl

# Set page configuration with Bootstrap theme
st.set_page_config(
    page_title='Splunk CIM Selection',
    layout='wide'
)


def safe_load_players():
    if 'data' in st.session_state:
        return st.session_state['data']['players']
    else:
        st.stop()


def safe_load_settings():
    if 'data' in st.session_state:
        return st.session_state['data']['game_settings']
    else:
        st.stop()


eastern_bloc = [
    'Russia', 'Azerbaijan', 'Kyrgyzstan', 'Tajikistan', 'Turkmenistan', 'Ukraine', 'Uzbekistan', 'Mongolia', 'Bulgaria',
    'Romania', 'Serbia', 'Slovenia', 'Bosnia and Herzegovina', 'Montenegro', 'North Macedonia', 'Slovakia',
    'Czech Republic', 'Estonia', 'Lithuania', 'Poland', 'Hungary', 'Kosovo', 'Germany', 'Pakistan', 'Belarus',
    'Kazakhstan', 'Latvia', 'Ukraine', 'Armenia', 'Georgia', 'Moldova', 'Uzbekistan', 'China', 'Finland', 'Sweden',
    'Norway', 'Denmark', 'Iceland', 'Austria', 'Belgium', 'France', 'Ireland', 'Italy', 'Luxembourg', 'Netherlands',
    'Switzerland', 'Portugal', 'Spain', 'United Kingdom', 'Greece', 'Turkey', 'Cyprus', 'Malta', 'Albania', 'Andorra',
    'Croatia', 'Gibraltar', 'Holy See', 'Monaco', 'San Marino'
]


def main():
    game_settings = safe_load_settings()
    draft = (
        safe_load_players()
        .filter(
            (pl.col('tid') == -2) & (pl.col('season') == game_settings['season']) & (
                    pl.col('draft_year') == game_settings['season'])
        )
        .with_columns(
            c_upper_bound=6 * 10 ** -6 * (pl.col('ovr') + 7) ** 4.0923,
            w_upper_bound=1 * 10 ** -8 * (pl.col('ovr') + 6) ** 5.6462,
            d_upper_bound=5 * 10 ** -5 * (pl.col('ovr') + 8) ** 3.5338,
            g_upper_bound=0.005 * (pl.col('ovr') + 10) ** 2.3515,
        )
        .with_columns(
            upper=(
                pl.when(pl.col('pos') == 'C')
                .then(pl.col('c_upper_bound'))
                .when(pl.col('pos') == 'W')
                .then(pl.col('w_upper_bound'))
                .when(pl.col('pos') == 'D')
                .then(pl.col('d_upper_bound'))
                .otherwise(pl.col('g_upper_bound'))
            )
        )
        .with_columns(
            sort_value=(3 * pl.col('max_value') + pl.col('sum_value')) / 10,
            short=(0.27 * (pl.col('sum_value')) - 5 * 0.75).clip(0),
            long=(0.61 * (pl.col('sum_value')) - 7 * 1.07).clip(0),
            u_short=(0.27 * (pl.col('upper')) - 5 * 0.75).clip(0),
            u_long=(0.61 * (pl.col('upper')) - 7 * 1.07).clip(0),
        )
        .with_columns(
            pl.col('u_short').truediv(4).alias('avg_short'),
            pl.col('short').alias('value'),
            pl.col('u_short').alias('upper')
        )
        .with_columns(
            (5 + ((pl.col('value') - pl.mean('value')) / pl.std('value'))).alias('value_z'),
            (5 + ((pl.col('upper') - pl.mean('upper')) / pl.std('upper'))).alias('upper_z'),
            (5 + ((pl.col('sort_value') - pl.mean('sort_value')) / pl.std('sort_value'))).alias('sort_value_z'),
        )
    )

    if draft["value"].sum() > 0:
        draft = (
            draft
            .with_columns(
                (pl.col('value_z') + pl.col('upper_z') + pl.col('sort_value_z')).alias('comp')
            )
            .with_columns(
                (pl.mean('value') + pl.std('value') * (pl.col('comp') - pl.mean('comp')).truediv(pl.std('comp'))).alias('comp_z'),
            )
        )
    elif draft["upper"].sum() > 0:
        draft = (
            draft
            .with_columns(
                (pl.col('upper_z') + pl.col('sort_value_z')).alias('comp')
            )
            .with_columns(
                (pl.mean('upper') + pl.std('upper') * (pl.col('comp') - pl.mean('comp')).truediv(pl.std('comp'))).alias('comp_z'),
            )
        )
    else:
        draft = (
            draft
            .with_columns(
                (pl.col('sort_value_z')).alias('comp')
            )
            .with_columns(
                (pl.mean('sort_value') + pl.std('sort_value') * (pl.col('comp') - pl.mean('comp')).truediv(pl.std('comp'))).alias('comp_z'),
            )
        )

    draft = draft.to_pandas()

    draft.insert(0, "Drafted", False)

    # Get dataframe row-selections from user with st.data_editor
    st.markdown("""# Draft Guide""", unsafe_allow_html=True)
    st.markdown("""------------------------------""")
    st.markdown("""### Available Players""", unsafe_allow_html=True)

    edited_df = st.data_editor(
        draft[
            ['player', 'pos', 'age', 'ovr', 'pot', 'sum_value', 'value', 'upper', 'sort_value', 'comp','comp_z']]
        .sort_values('sort_value', ascending=False).style
        .background_gradient(cmap='RdBu_r', vmin=10, vmax=70,
                             subset=['ovr', 'pot'])
        .background_gradient(cmap='RdBu_r', vmin=0, vmax=draft['sum_value'].max(),
                             subset=['sum_value'])
        .background_gradient(cmap='RdBu_r', vmin=0, vmax=draft[draft.Drafted == False]['sort_value'].max(),
                             subset=['sort_value'])
        .background_gradient(cmap='RdBu_r', vmin=0, vmax=draft[draft.Drafted == False]['value'].max(),
                             subset=['value'])
        .background_gradient(cmap='RdBu_r', vmin=0, vmax=draft[draft.Drafted == False]['upper'].max(),
                             subset=['upper'])
        .background_gradient(cmap='RdBu_r', vmin=0, vmax=draft[draft.Drafted == False]['comp'].max(),
                             subset=['comp'])
        .background_gradient(cmap='RdBu_r', vmin=0, vmax=draft[draft.Drafted == False]['comp_z'].max(),
                                subset=['comp_z'])
        .format(precision=1)
        .format(precision=0, subset=['ovr', 'pot']),
        hide_index=True,
        disabled=['max_value', 'sum_value', 'sort_value', 'short', 'long', 'value', 'upper', 'comp','comp_z', 'ovr', 'pot'],
        use_container_width=True
    )


if __name__ == '__main__':
    main()
