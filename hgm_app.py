import streamlit as st
import polars as pl
from hgm.data.process_data import load_and_process_players
from hgm.config import DATA_DIR

# Set page configuration with Bootstrap theme
st.set_page_config(
    page_title='Splunk CIM Documentation',
    layout='centered',
    page_icon=':open_file_folder:'
)


def upload_json():
    return st.file_uploader('Upload a JSON file', type='json')


def load_teams(json_data):
    # logger.info('Loading teams')
    return (
        json_data.select('teams').explode('teams').unnest('teams')
        .filter(pl.col('disabled') == False)
        .select('tid', pl.col('abbrev').alias('team'), )
        .extend(pl.DataFrame({'tid': [-2, -1], 'team': ['Draft', 'FA']}))
    )


def load_players(json_data, team_data, settings):
    # logger.info('Loading players')
    n_teams = int(32)
    players_raw = json_data.select('players').explode('players').unnest('players').lazy()
    birth_places = (
        players_raw
        .select(pl.col('pid'), pl.col('born'))
        .unnest('born')
        .select(
            pl.col('pid'),
            pl.col('loc').str.split(', ').list[-1].alias('country')
        )
    )
    progression = pl.scan_parquet(DATA_DIR / 'constants' / 'calculated_progs.parquet')
    return (
        load_and_process_players(players_raw, progression, settings)
        .join(birth_places.collect(), on='pid', how='left')
        .join(team_data, on='tid', how='left')
        .with_columns(is_current=pl.col('status') == 'current')
        .with_columns(years=pl.col('is_current').sum().over('pid'))
        .with_columns(max_value=pl.col('value').max().over('pid'))
        .with_columns(sum_value=pl.col('value').sum().over('pid'))
        .with_columns(p_rk=pl.col('ovr').rank(method='ordinal', descending=True).over(['season', 'pos']))
        .with_columns(
            is_prospect=pl.when((pl.col('age') <= 21) & (pl.col('team') != 'Draft')).then(pl.lit(True)).otherwise(
                pl.lit(False)))
        .with_columns(pr_rk=(
            pl.when(pl.col('is_prospect') == True)
            .then(pl.col('sum_value').rank(method='ordinal', descending=True).over(['season', 'is_prospect']))
            .otherwise(pl.lit(None))
        ))
        .with_columns(pr_rk_pos=(
            pl.when(pl.col('is_prospect') == True)
            .then(pl.col('sum_value').rank(method='ordinal', descending=True).over(['season', 'pos', 'is_prospect']))
            .otherwise(pl.lit(None))
        ))
        .with_columns(line=(
            pl.when((pl.col('pos') == 'G') & (pl.col('p_rk') <= n_teams)).then(pl.lit('Starter'))
            .when((pl.col('pos') == 'G') & (pl.col('p_rk').is_between(n_teams + 1, 2 * n_teams))).then(pl.lit('Backup'))
            .when((pl.col('pos') == 'C') & (pl.col('p_rk') <= n_teams)).then(pl.lit('1st Line'))
            .when((pl.col('pos') == 'C') & (pl.col('p_rk').is_between(n_teams + 1, 2 * n_teams))).then(
                pl.lit('2nd Line'))
            .when((pl.col('pos') == 'C') & (pl.col('p_rk').is_between(2 * n_teams + 1, 3 * n_teams))).then(
                pl.lit('3rd Line'))
            .when((pl.col('pos') == 'C') & (pl.col('p_rk').is_between(3 * n_teams + 1, 4 * n_teams))).then(
                pl.lit('4th Line'))
            .when((pl.col('pos') == 'W') & (pl.col('p_rk') <= 2 * n_teams)).then(pl.lit('1st Line'))
            .when((pl.col('pos') == 'W') & (pl.col('p_rk').is_between(2 * n_teams + 1, 4 * n_teams))).then(
                pl.lit('2nd Line'))
            .when((pl.col('pos') == 'W') & (pl.col('p_rk').is_between(4 * n_teams + 1, 6 * n_teams))).then(
                pl.lit('3rd Line'))
            .when((pl.col('pos') == 'W') & (pl.col('p_rk').is_between(6 * n_teams + 1, 8 * n_teams))).then(
                pl.lit('4th Line'))
            .when((pl.col('pos') == 'D') & (pl.col('p_rk') <= 2 * n_teams)).then(pl.lit('1st Pair'))
            .when((pl.col('pos') == 'D') & (pl.col('p_rk').is_between(2 * n_teams + 1, 4 * n_teams))).then(
                pl.lit('2nd Pair'))
            .when((pl.col('pos') == 'D') & (pl.col('p_rk').is_between(4 * n_teams + 1, 6 * n_teams))).then(
                pl.lit('3rd Pair'))
            .otherwise(pl.lit('Reserve'))
        ))
    )


def main():
    if 'data' not in st.session_state:
        st.session_state['data'] = None

    if st.button("Clear Data"):
        st.session_state['data'] = None
        st.rerun()

    if not st.session_state['data']:
        json_file = upload_json()
        pl_json = pl.read_json(json_file)
        game_settings = pl_json.select('gameAttributes').item()
        teams = load_teams(pl_json)
        players = load_players(pl_json, teams, game_settings)
        st.session_state['data'] = {
            'game_settings': game_settings,
            'teams': teams,
            'players': players
        }
        st.success('Data loaded successfully.')
    else:
        st.success('Data already loaded.')


if __name__ == '__main__':
    main()
