import streamlit as st
import pandas as pd
import plotly.express as px
import pgeocode
import time
import os
import uuid

# ----------------------------
# PAGE SETUP
# ----------------------------
st.set_page_config(
    page_title="Strategic Accounts Ownership Explorer",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Strategic Accounts Ownership Explorer — Map & Filters")
st.sidebar.title("🏠 Home — Map & Filters")
st.caption("Filter by Customer, SAM, State, or ZIP. View coverage on the map.")

# ----------------------------
# FILE PATHS
# ----------------------------
MAIN_PATH = "Strategic_Account_Ownership_Master.xlsx"
HELPER_PATH = "State_Contacts.xlsx"

# ----------------------------
# LOAD DATA
# ----------------------------
@st.cache_data(ttl=60)
def load_data():
    # Load main and helper files
    df_main = pd.read_excel(MAIN_PATH, sheet_name="Database")
    df_helper = pd.read_excel(HELPER_PATH, sheet_name="Contacts")

    df_main.columns = df_main.columns.str.strip()
    df_helper.columns = df_helper.columns.str.strip()

    # Normalize state names
    df_main["State"] = df_main["State"].astype(str).str.strip().str.upper()
    df_helper["State"] = df_helper["State"].astype(str).str.strip().str.upper()

    # Merge by state
    df = df_main.merge(df_helper, on="State", how="left", suffixes=("", "_Helper"))

    # Clean ZIP codes
    if "ZIP" not in df.columns:
        zc = [c for c in df.columns if "zip" in c.lower()]
        if zc:
            df.rename(columns={zc[0]: "ZIP"}, inplace=True)
    df["ZIP"] = df["ZIP"].astype(str).str.extract(r"(\d{5})", expand=False).fillna("")

    # Load Wausau Locations
    try:
        df_wausau = pd.read_excel(HELPER_PATH, sheet_name="Wausau Locations")
        df_wausau.columns = df_wausau.columns.str.strip()
        keep_cols = [c for c in ["Warehouse", "City", "State", "ZIP"] if c in df_wausau.columns]
        df_wausau = df_wausau[keep_cols].copy()
        df_wausau["State"] = df_wausau["State"].astype(str).str.strip().str.upper()
        df_wausau["ZIP"] = df_wausau["ZIP"].astype(str).str.extract(r"(\d{5})", expand=False).fillna("")
    except Exception as e:
        st.warning(f"⚠️ Could not load Wausau Locations tab: {e}")
        df_wausau = pd.DataFrame(columns=["Warehouse", "City", "State", "ZIP"])

    ts = time.strftime("%b %d, %Y %I:%M %p", time.localtime(os.path.getmtime(HELPER_PATH)))
    msg = f"✅ Data loaded successfully • last updated {ts}"

    return df, df_wausau, msg

df, df_wausau, msg = load_data()
st.markdown(f"<div style='color:#22c55e;font-weight:600'>{msg}</div>", unsafe_allow_html=True)

# ----------------------------
# SIDEBAR FILTERS (Cascading Logic)
# ----------------------------
st.sidebar.header("🔍 Filters")

if "suffix" not in st.session_state:
    st.session_state["suffix"] = str(uuid.uuid4())

if st.sidebar.button("🔄 Reset Filters"):
    for k in list(st.session_state.keys()):
        if any(x in k for x in ["cust_", "sam_", "state_", "zip_", "filters"]):
            st.session_state.pop(k, None)
    st.session_state["suffix"] = str(uuid.uuid4())
    st.sidebar.success("✅ Filters reset.")
    st.rerun()

sfx = st.session_state["suffix"]

# Begin cascading filters
filtered_opts = df.copy()

# State filter (drives all others)
states = sorted(df["State"].dropna().unique())
sel_state = st.sidebar.multiselect("State(s)", states, key=f"state_{sfx}")
if sel_state:
    filtered_opts = filtered_opts[filtered_opts["State"].isin(sel_state)]

# Customer filter
customers = sorted(filtered_opts["Customer"].dropna().unique())
sel_customer = st.sidebar.multiselect("Customer(s)", customers, key=f"cust_{sfx}")
if sel_customer:
    filtered_opts = filtered_opts[filtered_opts["Customer"].isin(sel_customer)]

# SAM filter
sams = sorted(filtered_opts["WSC_SAM"].dropna().unique())
sel_sam = st.sidebar.multiselect("SAM(s)", sams, key=f"sam_{sfx}")
if sel_sam:
    filtered_opts = filtered_opts[filtered_opts["WSC_SAM"].isin(sel_sam)]

# ZIP filter
zips = sorted(filtered_opts["ZIP"].dropna().unique())
sel_zip = st.sidebar.multiselect("ZIP(s)", zips, key=f"zip_{sfx}")

# Apply final filters to dataset
filtered = df.copy()
if sel_state:
    filtered = filtered[filtered["State"].isin(sel_state)]
if sel_customer:
    filtered = filtered[filtered["Customer"].isin(sel_customer)]
if sel_sam:
    filtered = filtered[filtered["WSC_SAM"].isin(sel_sam)]
if sel_zip:
    filtered = filtered[filtered["ZIP"].isin(sel_zip)]

# ----------------------------
# WAUSAU BRANCH TABLE (filters by state)
# ----------------------------
st.subheader("🏭 Wausau Branch Locations")

branch_display = df_wausau.copy()
if sel_state:
    branch_display = branch_display[branch_display["State"].isin(sel_state)]

st.markdown(f"Showing **{len(branch_display)}** of {len(df_wausau)} total Wausau branches.")
st.dataframe(branch_display, use_container_width=True, hide_index=True)

# ----------------------------
# GEOCODING FOR CUSTOMER MAP
# ----------------------------
@st.cache_data
def geocode(zipcodes):
    nomi = pgeocode.Nominatim("US")
    zips = list(set(zipcodes))
    result = nomi.query_postal_code(zips)
    result = result.rename(columns={"postal_code": "ZIP", "latitude": "lat", "longitude": "lon"})
    result["ZIP"] = result["ZIP"].astype(str)
    return result[["ZIP", "lat", "lon"]]

geo_main = filtered.merge(geocode(filtered["ZIP"]), on="ZIP", how="left")
geo_main = geo_main.dropna(subset=["lat", "lon"])

# ----------------------------
# CUSTOMER MAP
# ----------------------------
st.subheader(f"🗺️ Map View — {len(geo_main):,} Matching Records")
map_type = st.radio("Map Type", ["Pin Map", "Heatmap"], horizontal=True, key="map_type_home")

if map_type == "Pin Map":
    fig = px.scatter_mapbox(
        geo_main,
        lat="lat",
        lon="lon",
        color="Customer",
        hover_name="Customer",
        hover_data=["State", "ZIP", "WSC_Contact", "WSC_Title"] if "WSC_Contact" in geo_main.columns else ["State", "ZIP"],
        zoom=3,
        height=600,
    )
else:
    fig = px.density_mapbox(
        geo_main,
        lat="lat",
        lon="lon",
        radius=10,
        hover_name="Customer",
        zoom=3,
        height=600,
    )

fig.update_layout(
    mapbox_style="carto-positron",
    margin=dict(l=0, r=0, t=0, b=0),
)
st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# SAVE FILTERS FOR PAGE 2
# ----------------------------
st.session_state["filters"] = {
    "Customer": sel_customer,
    "SAM": sel_sam,
    "State": sel_state,
    "ZIP": sel_zip,
}
