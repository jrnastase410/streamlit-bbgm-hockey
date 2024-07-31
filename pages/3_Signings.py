import streamlit as st
import polars as pl
import numpy as np

# Set page configuration with Bootstrap theme
st.set_page_config(
    page_title='Show All',
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


def main():
    settings = safe_load_settings()
    my_team_id = settings['userTid'][-1]['value']
    signings = (
        safe_load_players()
        #.filter(pl.col('tid').is_in([my_team_id, -1]))
        .with_columns(info=pl.col('player') + ' (' + pl.col('team') + ')' + ' - ' + pl.col('pid').cast(pl.String))
        .sort(pl.col('pid'))
    )

    selection = st.selectbox(
        'Select a player',
        options=signings.filter(pl.col('season') == settings['season']).sort('pid','tid', 'player', descending=False)[
            'info'].to_list()
    )
    st.write('You selected:', selection)
    player_id = int(selection.split(' - ')[1])
    st.write('Player ID:', player_id)

    df_filtered = signings.filter(pl.col('pid') == player_id)
    st.dataframe(
        df_filtered.select(['player', 'season', 'age', 'ovr', 'pot', 'value', 'salary'])
    )

    num_options = 5

    for i in range(num_options):
        st.write(f'Option {i + 1}')
        num_years = st.slider('Enter the number of years', min_value=1, max_value=5, step=1, key=f'{i}years')

        # Get salary from the user
        salary = st.slider('Enter the salary', min_value=0.0, max_value=13.0,
                           step=0.1, key=f'{i}salary')

        new_salaries = pl.Series('salary', [salary] * num_years, dtype=pl.Float64)
        new_values = df_filtered['value'][1:1 + num_years]
        new_surplus = new_values - new_salaries

        st.dataframe(
            pl.DataFrame({
                'Total Cost': f'{np.round(new_salaries.sum(), 2)}M',
                'Player Value': f'{np.round(new_values.sum(), 2)}M',
                'Surplus': f'{np.round(new_surplus.sum(), 2)}M'}))


if __name__ == '__main__':
    main()
