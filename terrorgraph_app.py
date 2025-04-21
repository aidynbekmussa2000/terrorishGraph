import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="TerrorGraph", layout="wide")

# ----------------------------
# Load Data
# ----------------------------
@st.cache_data
def load_data():
    # Connect to your Neo4j Aura DB
    graph = Graph("neo4j+s://e05f068d.databases.neo4j.io", auth=("neo4j", "your-password"))

    # Run Cypher query to fetch data
    query = """
    MATCH (e:Event)
    RETURN
        e.year AS year,
        e.group AS gname,
        e.country AS country_txt,
        e.city AS city,
        e.attack_type AS attacktype1_txt,
        e.nkill AS nkill,
        e.nwound AS nwound
    """

    df = graph.run(query).to_data_frame()
    df['iyear'] = df['year'].astype(int)

    # Optional cleaning
    df['nkill'] = df['nkill'].fillna(0)
    df['nwound'] = df['nwound'].fillna(0)
    df['summary'] = ""  # if needed for keyword search fallback

    return df

df = load_data()

# ----------------------------
# Safe Slider Helper
# ----------------------------
def safe_slider(label, min_val, max_val, default_val=None):
    if min_val == max_val:
        st.write(f"🔒 {label}: only one value available ({min_val})")
        return min_val
    return st.slider(label, min_val, max_val, default_val or min_val)

# ----------------------------
# Title
# ----------------------------
st.title("📊 TerrorGraph Explorer")
st.markdown("Explore global terrorism trends by group, country, and year range.")
st.markdown("---")

# ----------------------------
# Sidebar Filters
# ----------------------------
with st.sidebar:
    st.header("🔍 Filter Options")

    group_list = sorted(df['gname'].dropna().unique())
    group = st.selectbox("Select Group:", group_list)

    filtered_by_group = df[df['gname'] == group]
    country_list = sorted(filtered_by_group['country_txt'].dropna().unique())
    country = st.selectbox("Select Country:", country_list)

    min_year = int(filtered_by_group['iyear'].min()) if not filtered_by_group.empty else int(df['iyear'].min())
    max_year = int(filtered_by_group['iyear'].max()) if not filtered_by_group.empty else int(df['iyear'].max())
    year_range = safe_slider("Year Range", min_year, max_year, (min_year, max_year))

    attack_types = sorted(filtered_by_group['attacktype1_txt'].dropna().unique())
    selected_types = st.multiselect("Attack Types", attack_types, default=attack_types)

    min_kills = int(filtered_by_group['nkill'].fillna(0).min())
    max_kills = int(filtered_by_group['nkill'].fillna(0).max())
    kill_filter = safe_slider("Minimum Fatalities", min_kills, max_kills)

    keyword = st.text_input("Keyword in Summary")

# ----------------------------
# Apply Filters
# ----------------------------
filtered = filtered_by_group[
    (filtered_by_group['country_txt'] == country) &
    (filtered_by_group['iyear'].between(year_range[0], year_range[1]) if isinstance(year_range, tuple) else filtered_by_group['iyear'] == year_range) &
    (filtered_by_group['attacktype1_txt'].isin(selected_types)) &
    (filtered_by_group['nkill'].fillna(0) >= kill_filter)
]

if keyword:
    filtered = filtered[filtered['summary'].str.contains(keyword, case=False, na=False)]

# ----------------------------
# Show Summary or Warning
# ----------------------------
if filtered.empty:
    st.warning("⚠️ No events found. Try adjusting your filters.")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Total Events", len(filtered))
col2.metric("Fatalities", int(filtered['nkill'].sum()))
col3.metric("Countries", filtered['country_txt'].nunique())

# ----------------------------
# Tabs for Output
# ----------------------------
tab1, tab2, tab3 = st.tabs(["📋 Data Table", "📈 Yearly Chart", "🗺️ Event Map"])

with tab1:
    st.dataframe(filtered[['date', 'city', 'attacktype1_txt', 'nkill', 'nwound', 'summary']].reset_index(drop=True))

with tab2:
    chart = px.histogram(filtered, x='iyear', nbins=(year_range[1] - year_range[0] + 1) if isinstance(year_range, tuple) else 1,
                         title='Attacks Per Year', labels={'iyear': 'Year'})
    st.plotly_chart(chart, use_container_width=True)

with tab3:
    if 'latitude' in filtered.columns and 'longitude' in filtered.columns:
        filtered_geo = filtered.dropna(subset=['latitude', 'longitude'])
        if not filtered_geo.empty:
            fig = px.scatter_geo(filtered_geo,
                                 lat='latitude', lon='longitude',
                                 hover_name='city',
                                 color='attacktype1_txt',
                                 size='nkill',
                                 projection="natural earth",
                                 title="Terror Events Map")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No geolocation data available.")
    else:
        st.info("Geolocation columns missing.")

# ----------------------------
# Download Filtered Results
# ----------------------------
@st.cache_data
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8')

csv = convert_df(filtered)
st.download_button("📥 Download Filtered Data", csv, "filtered_terror_data.csv", "text/csv")
