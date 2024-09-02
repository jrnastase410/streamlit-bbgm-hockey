import streamlit as st
import polars as pl

from hgm.plots.player_plots import player_plot

# Set page configuration with Bootstrap theme
st.set_page_config(
    page_title='Splunk Source List',
    layout='wide'
)


def safe_load_players():
    if 'data' in st.session_state:
        return st.session_state['data']['players']
    else:
        st.stop()


def safe_load_teams():
    if 'data' in st.session_state:
        return st.session_state['data']['teams']
    else:
        st.stop()


def safe_load_settings():
    if 'data' in st.session_state:
        return st.session_state['data']['game_settings']
    else:
        st.stop()


def select_teams(df: pl.DataFrame):
    teams_to_choose_from = (
            ['*All*'] + ['FA', 'Draft'] +
            df.filter(pl.col('tid') > -1).unique('tid', keep='last')['team'].sort().to_list()
    )

    num_columns = 10
    num_per_column = len(teams_to_choose_from) // num_columns + 1
    columns = st.columns(num_columns)
    selected_teams = []

    # Use a single counter for all checkboxes
    checkbox_counter = 0

    for i in range(num_columns):
        for team in teams_to_choose_from[i * num_per_column: (i + 1) * num_per_column]:
            selected = columns[i].checkbox(team, key=f"team_checkbox_{checkbox_counter}")
            checkbox_counter += 1  # Increment the counter for each checkbox
            if selected:
                selected_teams.append(team)
    return selected_teams


def filter_teams(df, selected_teams):
    if selected_teams != ['*All*']:
        return df.filter(pl.col('team').is_in(selected_teams))
    else:
        return df


def display_and_select_pids(df):
    df = df.to_pandas()
    if 'selected_pids' not in st.session_state:
        st.session_state.selected_pids = []

    df_with_selections = df.copy()
    df_with_selections.insert(0, "Select", False)

    # Get dataframe row-selections from user with st.data_editor
    edited_df = st.data_editor(
        (
            df_with_selections
            .style
            .format(precision=0, subset=['pid', 'draft_year', 'age', 'ovr', 'pot', 'pr_rk', 'pr_rk_pos'])
            .format(precision=2, subset=['sum_value'])
            .background_gradient(cmap='RdBu_r', vmin=26, vmax=80, subset=['ovr', 'pot'])
            .background_gradient(cmap='RdBu_r', vmin=-150, vmax=150, subset=['sum_value'])
        )
        ,
        hide_index=True,
        column_config={"Select": st.column_config.CheckboxColumn(required=True)},
        disabled=df.columns,
        use_container_width=True
    )

    # Filter the dataframe using the temporary column, then drop the column
    selected_pids = list(set(edited_df[edited_df.Select]['pid'].to_list() + st.session_state.selected_pids))
    return selected_pids


def main():
    players = safe_load_players().filter(pl.col('age') <= 21)
    teams = safe_load_teams()
    settings = safe_load_settings()
    my_team_id = settings['userTid'][-1]['value']
    st.markdown(
        f"Season: {settings['season']}, "
        f"My Team: {players.filter(pl.col('tid') == my_team_id).select(pl.first('team')).item()}"
    )

    selected_teams = select_teams(teams)

    df_filtered = filter_teams(players, selected_teams)
    selected_position = st.selectbox('Select Position', options=['All', 'C', 'W', 'D', 'G'])
    if selected_position != 'All':
        df_filtered = df_filtered.filter(pl.col('pos') == selected_position)

    if st.button('Clear selected players'):
        st.session_state['selected_pids'] = []

    df_display = (
        df_filtered
        .filter(pl.col('season') == settings['season'])
        .select(
            'player', 'pid', 'draft_year', 'team', 'pos', 'age', 'pr_rk', 'pr_rk_pos', 'ovr', 'pot', pl.col('sum_value')
        )
        .sort('sum_value', descending=True)
    )

    filter_dict = {
        'Upcoming FA': (pl.col('years') == 1),
        'Dead Weight': (pl.col('years') > 1) & (pl.col('cv_total') < 0)
    }

    filters_to_apply = []

    filter_columns = st.columns(2)
    for i, filter_type in enumerate(filter_dict.keys()):
        selection = filter_columns[i].checkbox(filter_type)
        if selection:
            filters_to_apply.append(filter_dict[filter_type])

    if filters_to_apply:
        df_display = df_display.filter(filters_to_apply)

    display_and_select_pids(df_display)

    st.dataframe(
        players
        .filter(pl.col('season') == settings['season'])
        .filter(pl.col('tid') >= 0)
        .with_columns(
            top_10=pl.col('pr_rk') <= 10,
            top_50=pl.col('pr_rk') <= 50,
            top_100=pl.col('pr_rk') <= 100,
        )
        .group_by('team')
        .agg(
            pl.sum('top_10').alias('top_10'),
            pl.sum('top_50').alias('top_50'),
            pl.sum('top_100').alias('top_100'),
            pl.sum('sum_value'),
        )
        .sort('sum_value', descending=True))


if __name__ == '__main__':
    main()
