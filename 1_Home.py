import streamlit as st
import pandas as pd
import plotly.express as px
import pgeocode
import time
import os
import uuid

# ----------------------------
# Page setup
# ----------------------------
st.set_page_config(
    page_title="Strategic Accounts Ownership Explorer",
    page_icon="Favicon.png",
    layout="wide",
)
st.title("📊 Strategic Accounts Ownership Explorer — Map & Filters")
st.sidebar.title("🏠 Home — Map & Filters")
st.caption("Filter by Customer, SAM, State, or ZIP. View coverage on the map.")

# ----------------------------
# File paths
# ----------------------------
MAIN_PATH = "Strategic_Account_Ownership_Master.xlsx"
HELPER_PATH = "State_Contacts.xlsx"

@st.cache_data(ttl=60)
def load_data():
    df_main = pd.read_excel(MAIN_PATH, sheet_name="Database")
    df_helper = pd.read_excel(HELPER_PATH, sheet_name="Contacts")

    # Clean helper
    df_helper = df_helper.loc[:, ~df_helper.columns.astype(str).str.startswith("Unnamed")]
    df_main.columns = df_main.columns.str.strip()
    df_helper.columns = df_helper.columns.str.strip()

    # Normalize keys
    df_main["State"] = df_main["State"].astype(str).str.strip().str.upper()
    df_helper["State"] = df_helper["State"].astype(str).str.strip().str.upper()

    # Merge by State
    df = df_main.merge(df_helper, on="State", how="left", suffixes=("", "_Helper"))

    # Standardize ZIP
    if "ZIP" not in df.columns:
        zip_col = [c for c in df.columns if "zip" in c.lower()]
        if zip_col:
            df.rename(columns={zip_col[0]: "ZIP"}, inplace=True)
    df["ZIP"] = df["ZIP"].astype(str).str.extract(r"(\d{5})", expand=False).fillna("")

    ts = time.strftime("%b %d, %Y %I:%M %p", time.localtime(os.path.getmtime(HELPER_PATH)))
    msg = f"✅ Helper file merged successfully • last updated {ts}"
    return df, msg

df, msg = load_data()
st.markdown(f"<div style='color:#22c55e;font-weight:600'>{msg}</div>", unsafe_allow_html=True)

# ----------------------------
# Sidebar filters
# ----------------------------
st.sidebar.header("🔍 Filters")

# Ensure widget suffix is initialized once
if "suffix" not in st.session_state:
    st.session_state["suffix"] = str(uuid.uuid4())

# Reset button clears selections but keeps stable widget keys
if st.sidebar.button("🔄 Reset Filters"):
    for key in list(st.session_state.keys()):
        if key.startswith(("cust_", "sam_", "state_", "zip_")):
            del st.session_state[key]
    st.rerun()

sfx = st.session_state["suffix"]


customers = sorted(df["Customer"].dropna().unique())
sel_customer = st.sidebar.multiselect("Customer(s)", customers, key=f"cust_{sfx}")

sams = sorted(df["WSC_SAM"].dropna().unique())
sel_sam = st.sidebar.multiselect("SAM(s)", sams, key=f"sam_{sfx}")

states = sorted(df["State"].dropna().unique())
sel_state = st.sidebar.multiselect("State(s)", states, key=f"state_{sfx}")

zips = sorted(df["ZIP"].dropna().unique())
sel_zip = st.sidebar.multiselect("ZIP(s)", zips, key=f"zip_{sfx}")

# Filter dataset
filtered = df.copy()
if sel_customer:
    filtered = filtered[filtered["Customer"].isin(sel_customer)]
if sel_sam:
    filtered = filtered[filtered["WSC_SAM"].isin(sel_sam)]
if sel_state:
    filtered = filtered[filtered["State"].isin(sel_state)]
if sel_zip:
    filtered = filtered[filtered["ZIP"].isin(sel_zip)]

# ----------------------------
# Map
# ----------------------------
@st.cache_data
def geocode(zipcodes):
    nomi = pgeocode.Nominatim("US")
    result = nomi.query_postal_code(list(set(zipcodes)))
    result = result.rename(columns={"postal_code": "ZIP", "latitude": "lat", "longitude": "lon"})
    result["ZIP"] = result["ZIP"].astype(str)
    return result[["ZIP", "lat", "lon"]]

geo = geocode(filtered["ZIP"])
geo = filtered.merge(geo, on="ZIP", how="left")

st.subheader(f"🗺️ Map View — {len(geo):,} Matching Records")

map_type = st.radio("Map Type", ["Pin Map", "Heatmap"], horizontal=True)

if map_type == "Pin Map":
    fig = px.scatter_map(
        geo, lat="lat", lon="lon",
        color="Customer",
        hover_name="Customer",
        hover_data=["State", "ZIP", "WSC_Contact", "WSC_Title"],
        zoom=3, height=600
    )
else:
    fig = px.density_map(
        geo, lat="lat", lon="lon", radius=10,
        hover_name="Customer", zoom=3, height=600
    )

# ----------------------------
# Final Map Display & Layout
# ----------------------------
fig.update_layout(map_style="carto-positron", margin=dict(l=0, r=0, t=0, b=0))
st.plotly_chart(fig, use_container_width=True)

# Add spacing below map to prevent text overlap
st.markdown("<br><br>", unsafe_allow_html=True)

# Save filter selections for Page 2
st.session_state["filters"] = {
    "Customer": sel_customer,
    "SAM": sel_sam,
    "State": sel_state,
    "ZIP": sel_zip
}

# Navigation note styled cleanly
st.container().markdown(
    """
    💡 **Tip:** Navigate to **Page 2 → Ownership Details** using the sidebar  
    to view Customer and WSC Ownership contacts in table format.
    """,
    unsafe_allow_html=True
)

st.divider()


# ----------------------------
# Export filtered dataset
# ----------------------------
st.divider()
st.subheader("⬇️ Export Filtered Data")

if not filtered.empty:
    csv_data = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="💾 Export Current Filtered Data (CSV)",
        data=csv_data,
        file_name="Filtered_Accounts_Map_View.csv",
        mime="text/csv",
        use_container_width=True
    )
else:
    st.info("No data available for export based on current filters.")

# ----------------------------
# 🎥 Instructional Video Section
# ----------------------------
from pathlib import Path
import streamlit as st

st.markdown("---")
st.subheader("🎥 Instructional Video")

# Use Path to locate the video in the assets folder (works locally + Streamlit Cloud)
video_path = Path("assets/instructional_video.mp4")

if video_path.exists():
    # Optional: Expanded=True on first load for better visibility
    with st.expander("▶️ Watch Instructional Video (Click to Expand)", expanded=True):
        with open(video_path, "rb") as video_file:
            st.video(video_file.read())
else:
    st.warning(f"⚠️ Instructional video not found at: {video_path.resolve()}")


