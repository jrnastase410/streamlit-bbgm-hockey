import streamlit as st
import polars as pl

# Set page configuration with Bootstrap theme
st.set_page_config(
    page_title='Selection Guide',
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
    game_settings = safe_load_settings()
    draft = (
        safe_load_players()
        .filter(
            (pl.col('tid') == -2) & (pl.col('season') == game_settings['season']) & (
                    pl.col('draft_year') == game_settings['season'])
        )
        .to_pandas()
    )

    draft.insert(0, "Drafted", False)

    # Get dataframe row-selections from user with st.data_editor
    st.markdown("""# Draft Guide""", unsafe_allow_html=True)
    st.markdown("""------------------------------""")
    st.markdown("""### Available Players""", unsafe_allow_html=True)

    edited_df = st.data_editor(
        draft[['Drafted', 'player', 'pos', 'age', 'ovr', 'pot', 'max_value', 'sum_value', 'pid']]
        .sort_values('max_value', ascending=False).style
        .background_gradient(cmap='RdBu_r', vmin=26, vmax=80,
                             subset=['ovr', 'pot'])
        .background_gradient(cmap='RdBu_r', vmin=0, vmax=draft[draft.Drafted == False]['max_value'].max(),
                             subset=['max_value'])
        .background_gradient(cmap='RdBu_r', vmin=0, vmax=draft[draft.Drafted == False]['sum_value'].max(),
                             subset=['sum_value'])
        .format(precision=0)
        .format(precision=2, subset=['max_value', 'sum_value']),
        hide_index=True,
        column_config={"Drafted": st.column_config.CheckboxColumn(required=True)},
        disabled=['max_value', 'sum_value', 'ovr', 'pot'],
        use_container_width=True
    )

    drafted_df = edited_df[edited_df.Drafted]

    # Display the dataframes
    st.markdown("""### Drafted Players""", unsafe_allow_html=True)
    st.dataframe(drafted_df, use_container_width=True)


if __name__ == '__main__':
    main()
