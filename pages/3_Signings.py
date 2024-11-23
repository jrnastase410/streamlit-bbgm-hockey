import streamlit as st
import polars as pl
import numpy as np
from hgm.config import DATA_DIR

# Set page configuration with Bootstrap theme
st.set_page_config(
    page_title='Splunk Training Resource',
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


def calculate_percentile(df: pl.DataFrame, column: str, value: float) -> float:
    """
    Calculate the percentile of a given value in a Polars DataFrame column.

    :param df: Polars DataFrame
    :param column: Name of the column to calculate percentile for
    :param value: Value to find the percentile for
    :return: Percentile as a float between 0 and 100
    """
    # Extract the column as a numpy array
    col_values = df[column].to_numpy()

    # Calculate the percentile
    percentile = (col_values < value).mean() * 100

    return percentile

def calculate_letter_grade(percentile: float) -> str:
    """
    Calculate the letter grade for a given percentile.

    :param percentile: Percentile as a float between 0 and 100
    :return: Letter grade as a string
    """
    if percentile >= 95:
        return 'A+'
    elif percentile >= 90:
        return 'A'
    elif percentile >= 75:
        return 'B'
    elif percentile >= 50:
        return 'C'
    elif percentile >= 25:
        return 'D'
    else:
        return 'F'


def main():
    settings = safe_load_settings()
    my_team_id = settings['userTid'][-1]['value']
    signings = (
        safe_load_players()
        .with_columns(info=pl.col('player') + ' (' + pl.col('team') + ')' + ' - ' + pl.col('pid').cast(pl.String))
        .sort(pl.col('pid'))
    )
    contracts = pl.read_parquet(f'{DATA_DIR}/processed/contracts.parquet')

    st.write(
        calculate_percentile(df=contracts, column='avg_surplus', value=1.5)
    )

    selection = st.selectbox(
        'Select a player',
        options=signings.filter(pl.col('season') == settings['season']).sort('pid', 'tid', 'player', descending=False)[
            'info'].to_list()
    )
    st.write('You selected:', selection)
    player_id = int(selection.split(' - ')[1])
    st.write('Player ID:', player_id)

    df_filtered = signings.filter(pl.col('pid') == player_id)
    st.dataframe(
        df_filtered.select(['player', 'season', 'age', 'ovr', 'pot', 'value', 'salary'])
    )

    # Add checkbox for in-season signing
    is_in_season = st.checkbox('In-season signing')

    num_options = 8

    for i in range(num_options):
        st.write(f'{i + 1} year contract')
        num_years = i + 1

        # Get salary from the user
        salary = st.number_input('Enter the salary', min_value=0.0, max_value=14.0,
                                 step=0.1, key=f'{i}salary')

        new_salaries = pl.Series('salary', [salary] * num_years, dtype=pl.Float64)

        # Adjust the value calculation based on the in-season checkbox
        if is_in_season:
            new_values = df_filtered['value'][0:num_years]
        else:
            new_values = df_filtered['value'][1:1 + num_years]

        new_surplus = new_values - new_salaries
        total_cost = new_salaries.sum()
        total_value = new_values.sum()
        avg_surplus = new_surplus.mean()
        total_surplus = new_surplus.sum()
        avg_percentile = calculate_percentile(df=contracts, column='avg_surplus', value=avg_surplus)
        total_percentile = calculate_percentile(df=contracts, column='total_surplus', value=total_surplus)
        contract_grade = calculate_letter_grade(max(avg_percentile, total_percentile))

        st.dataframe(
            pl.DataFrame(
                {
                    'Total Cost': f'{np.round(total_cost, 2)}M',
                    'Player Value': f'{np.round(total_value, 2)}M',
                    'Avg. Surplus': f'{np.round(avg_surplus, 2)}M',
                    'Total Surplus': f'{np.round(total_surplus, 2)}M',
                    'Avg. %': f'{avg_percentile:.0f}%',
                    'Total %': f'{total_percentile:.0f}%',
                    'Grade': contract_grade
                },
            )
        )


if __name__ == '__main__':
    main()
