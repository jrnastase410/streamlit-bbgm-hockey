# %%
import polars as pl
import pickle

from hgm.config import MODELS_DIR

model_dict = {
    position: pickle.load(open(MODELS_DIR / 'ovr_to_cap' / f'{position}.pkl', 'rb'))
    for position in ['C', 'W', 'D', 'G']
}

salary_model = pickle.load(open(MODELS_DIR / 'salary' / 'xgboost_salary.pkl', 'rb'))


# %%
def map_positions(pos_column):
    return pos_column.replace({
        'C': 1,
        'W': 2,
        'D': 3,
        'G': 4
    }).cast(pl.Int32)


# %%
def load_players(player_data, progs_data, settings):
    player_ratings = (
        player_data
        .select('pid', 'tid', 'firstName', 'lastName', 'born', 'ratings')
        .with_columns(
            pl.concat_str(pl.col('firstName'), pl.lit(' '), pl.col('lastName')).alias('player'),
        )
        .explode('ratings')
        .unnest('ratings')
        .with_columns(
            age=pl.col('season') - pl.col('born').struct.field('year')
        )
        .unique(['pid', 'season'])
        .sort(['pid', 'season'])
        .select('player', 'pid', 'tid', 'season', 'age', 'pos', 'ovr')
        .filter(pl.col('season') >= settings['season'])
    )

    player_salaries = (
        player_data
        .select('pid', 'salaries')
        .explode('salaries')
        .unnest('salaries')
        .group_by(['pid', 'season'])
        .agg(salary=pl.col('amount').last())
        .sort('pid', 'season')
        .filter(pl.col('season') >= settings['season'])
    )

    player_draft_years = (
        player_data
        .select('pid', 'draft')
        .unnest('draft')
        .select('pid', pl.col('year').alias('draft_year'))
    )

    ovr_progs = (
        progs_data
        .filter(pl.col('variable').str.contains('ovr'))
        .select(
            pl.col('pos'),
            pl.col('age'),
            pl.col('ovr'),
            pl.col('variable').str.split('_').list.last().cast(pl.Int64).add(settings['season']).alias('season'),
            pl.col('value').alias('ovr_pred')
        )
    )

    value_progs = (
        progs_data
        .filter(pl.col('variable').str.contains('value'))
        .select(
            pl.col('pos'),
            pl.col('age'),
            pl.col('ovr'),
            pl.col('variable').str.split('_').list.last().cast(pl.Int64).add(settings['season']).alias('season'),
            pl.col('value').alias('value_pred')
        )
    )

    def assign_cap_values(pos_column: pl.Expr, ovr_column: pl.Expr, clip_value: int) -> pl.Expr:
        return (
            pl.when(pos_column == 'C').then(
                ovr_column * model_dict['C'].coef_[0] + model_dict['C'].intercept_[0])
            .when(pos_column == 'W').then(
                ovr_column * model_dict['W'].coef_[0] + model_dict['W'].intercept_[0])
            .when(pos_column == 'D').then(
                ovr_column * model_dict['D'].coef_[0] + model_dict['D'].intercept_[0])
            .when(pos_column == 'G').then(
                ovr_column * model_dict['G'].coef_[0] + model_dict['G'].intercept_[0])
            .clip(clip_value)
        )

    players = (
        player_ratings
        .with_columns(
            pl.Series('season', [range(settings['season'], settings['season'] + 10)], dtype=pl.List)
        )
        .explode('season')
        .join(player_salaries, on=['pid', 'season'], how='left')
        .join(player_draft_years, on='pid', how='left')
        .join(ovr_progs, on=['pos', 'age', 'season', 'ovr'], how='left')
        .join(value_progs, on=['pos', 'age', 'season', 'ovr'], how='left')
        .with_columns(
            cap_value=assign_cap_values(pl.col('pos'), pl.col('ovr'), 0)
        )
        .select(
            'player', 'pid', 'tid', 'season', 'pos', 'draft_year',
            age=pl.col('age') + pl.col('season') - settings['season'],
            salary=pl.col('salary') / 1000,
            ovr=pl.when(pl.col('season') == settings['season']).then(pl.col('ovr')).otherwise(pl.col('ovr_pred')),
            cap_value=pl.when(pl.col('season') == settings['season']).then(pl.col('cap_value')).otherwise(
                pl.col('value_pred'))
        )
        .filter(pl.col('season') >= settings['season'])
    )

    return players


# %%
def add_placeholder_salaries(df):
    last_contracts = (
        df
        .filter(pl.col('salary').is_not_null())
        .group_by('pid').tail(1)
        .select('pid', 'season', map_positions(pl.col('pos')), 'age', 'ovr', 'salary')
        .with_columns(
            season=pl.col('season').map_elements(lambda x: list(range(x + 1, x + 6)), return_dtype=pl.List(pl.Int64))
        )
        .explode('season')
    )

    last_contracts = (
        last_contracts
        .with_columns(on_last_contract=salary_model.predict(last_contracts.select(['pos', 'age', 'ovr', 'salary'])))
        .with_columns(pl.col('on_last_contract').mul(1.25).clip(0, 13))
    )

    no_contracts = (
        df
        .filter(pl.col('salary').first().over('pid').is_null())
        .group_by('pid').head(1)
        .select('pid', 'season', map_positions(pl.col('pos')), 'age', 'ovr', 'salary')
        .with_columns(
            season=pl.col('season').map_elements(lambda x: list(range(x, x + 5)), return_dtype=pl.List(pl.Int64))
        )
        .explode('season')
    )

    no_contracts = (
        no_contracts
        .with_columns(on_no_contract=salary_model.predict(no_contracts.select(['pos', 'age', 'ovr', 'salary'])))
        .with_columns(pl.col('on_no_contract').mul(1.25).clip(0, 13))
    )

    df = (
        df
        .join(last_contracts.select('pid', 'season', 'on_last_contract'), on=['pid', 'season'], how='left')
        .join(no_contracts.select('pid', 'season', 'on_no_contract'), on=['pid', 'season'], how='left')
        .with_columns(
            salary_next=(
                pl.when(pl.col('salary').is_not_null()).then(None)
                .otherwise(pl.col('on_last_contract').fill_null(pl.col('on_no_contract')))
            )
        )
        .drop('on_last_contract', 'on_no_contract')
    )

    return df


# %%
def add_contract_value(cap_value, salary):
    return cap_value - salary


# %%
def load_and_process_players(player_data, prog_data, settings):
    players = (
        load_players(player_data, prog_data, settings)
        .collect()
        .pipe(add_placeholder_salaries)
        .lazy()
        .with_columns(
            pot=pl.col('ovr').max().over('pid'),
            cap_surplus=add_contract_value(pl.col('cap_value'), pl.col('salary')),
            next_cap_surplus=add_contract_value(pl.col('cap_value'), pl.col('salary_next'))
        )
        .with_columns(
            contract_value=pl.col('cap_surplus').sum().over('pid'),
            next_contract_value=pl.col('next_cap_surplus').sum().over('pid')
        )
        .with_columns(
            total_contract_value=pl.col('contract_value') + pl.col('next_contract_value').clip(0),
            status=(
                pl.when(pl.col('salary').is_not_null()).then(pl.lit('current'))
                .when(pl.col('salary_next').is_not_null()).then(pl.lit('next'))
                .otherwise(pl.lit('none'))
            ).cast(pl.Categorical)
        )
        .select(
            'player', 'pid', 'tid', 'season', 'draft_year', 'pos', 'age', 'status', 'ovr', 'pot',
            value=pl.col('cap_value'),
            salary=(
                pl.when(pl.col('status') == 'current').then(pl.col('salary'))
                .when(pl.col('status') == 'next').then(pl.col('salary_next'))
                .otherwise(None)
            ),
            surplus=(
                pl.when(pl.col('status') == 'current').then(pl.col('cap_surplus'))
                .when(pl.col('status') == 'next').then(pl.col('next_cap_surplus'))
                .otherwise(None)
            ),
            cv_current=pl.col('contract_value'),
            cv_next=pl.col('next_contract_value'),
            cv_total=pl.col('total_contract_value'),
        )
        .collect()
    )
    return players
# %%
