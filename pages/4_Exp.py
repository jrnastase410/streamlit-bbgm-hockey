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
    expansion_df = pl.read_csv('C:/Users/jrnas/Downloads/Draft_Undrafted.csv')
    # Get Name column as a list
    expansion_players = expansion_df['Name'].to_list()
    return df.filter(pl.col('player').is_in(expansion_players))


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
            .format(precision=0, subset=['pid', 'age', 'ovr', 'pot', 'p_rk'])
            .format(precision=2, subset=['cv_current', 'cv_next', 'cv_total', 'value', 'salary', 'sum_value'])
            .background_gradient(cmap='RdBu_r', vmin=26, vmax=80, subset=['ovr', 'pot'])
            .background_gradient(cmap='RdBu_r', vmin=-50, vmax=50, subset=['cv_current'])
            .background_gradient(cmap='RdBu_r', vmin=-50, vmax=50, subset=['cv_next'])
            .background_gradient(cmap='RdBu_r', vmin=-50, vmax=50, subset=['cv_total'])
            .background_gradient(cmap='RdBu_r', vmin=-75, vmax=75, subset=['sum_value'])
            .background_gradient(cmap='RdBu_r', vmin=-15, vmax=15,
                                 subset=['value'])
            .background_gradient(cmap='RdBu_r', vmin=-13, vmax=13, subset=['salary'])
            .background_gradient(cmap='RdBu', vmin=0, vmax=10, subset=['years'])
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
    players = safe_load_players()
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
        .filter(pl.col('season') == settings['season'] + 1)
        .select(
            'player', 'pid', 'team', 'pos', 'age', 'p_rk', 'line', 'ovr', 'pot', 'years', 'salary',
            pl.col('value'), pl.col('sum_value'),
            pl.col('cv_current'), pl.col('cv_next'), pl.col('cv_total')
        )
        .sort('cv_total', descending=True)
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

    st.session_state['selected_pids'] = display_and_select_pids(df_display)

    selected_df = (
        players
        .filter(
            (pl.col('season') == settings['season']) &
            (pl.col('pid').is_in(st.session_state['selected_pids']))
        )
        .select(
            'player', 'team', 'pos', 'age', 'p_rk', 'pr_rk', 'ovr', pl.col('pot').round(0), 'years', 'salary',
            pl.col('value').round(2), pl.col('cv_current').round(2), pl.col('cv_total').round(2)
        )
        .sort('cv_total', descending=True)
    )

    selected_by_team_df = selected_df.group_by('team').agg(pl.sum('cv_current', 'cv_total')).sort('cv_total',
                                                                                                  descending=True)

    if st.checkbox('Trade'):
        col1, col2 = st.columns(2, gap='large')

        with col1:
            st.dataframe(selected_df, use_container_width=True, hide_index=True)

        with col2:
            st.dataframe(selected_by_team_df, hide_index=True)

    [st.plotly_chart(player_plot(players, pid), use_container_width=True)
     for pid in st.session_state['selected_pids']]

    st.dataframe(
        players
        .filter(pl.col('season') == settings['season'])
        .filter(pl.col('tid') >= 0)
        .select('team', 'value', 'cv_current', pl.col('cv_next').clip(0, ), 'cv_total')
        .group_by('team')
        .sum()
        .sort('cv_total', descending=True))


if __name__ == '__main__':
    main()
