import os
import re
import time
import uuid

import streamlit as st
import pandas as pd
import plotly.express as px
import pgeocode

# ----------------------------
# Page setup
# ----------------------------
st.set_page_config(
    page_title="Strategic Accounts Ownership Explorer",
    page_icon="Favicon.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.markdown("<link rel='apple-touch-icon' href='apple-touch-icon.png'>", unsafe_allow_html=True)

st.title("📊 Strategic Accounts Ownership Explorer")
st.caption("Cascading filters: Customer → SAM → State → ZIP. Dropdowns collapse automatically after selection.")

# ----------------------------
# File paths
# ----------------------------
MAIN_PATH = "Strategic_Account_Ownership_Master.xlsx"
MAIN_SHEET = "Database"
HELPER_PATH = "State_Contacts.xlsx"
HELPER_SHEET = "Contacts"

# ----------------------------
# Data loading & merge
# ----------------------------
@st.cache_data(ttl=60)
def load_and_merge():
    # Load main
    df_main = pd.read_excel(MAIN_PATH, sheet_name=MAIN_SHEET)
    df_main.columns = df_main.columns.str.strip()

    # Normalize ZIP in main (keep as string, 5 digits if present)
    zip_candidates_main = [c for c in df_main.columns if c.lower() in ("zip", "zipcode", "postal", "postal code")]
    if zip_candidates_main:
        main_zip_col = zip_candidates_main[0]
    else:
        main_zip_col = "ZIP" if "ZIP" in df_main.columns else None

    if main_zip_col:
        df_main[main_zip_col] = (
            df_main[main_zip_col].astype(str).str.extract(r"(\d{5})", expand=False).fillna("")
        )
        if main_zip_col != "ZIP":
            df_main.rename(columns={main_zip_col: "ZIP"}, inplace=True)

    # Normalize State in main
    if "State" in df_main.columns:
        df_main["State"] = df_main["State"].astype(str).str.strip().str.upper()

    # Load helper
    df_helper = pd.read_excel(HELPER_PATH, sheet_name=HELPER_SHEET)
    # Drop unnamed/empty columns
    df_helper = df_helper.loc[:, ~df_helper.columns.astype(str).str.startswith("Unnamed")]
    df_helper.columns = df_helper.columns.str.strip()

    # Normalize helper ZIP to string "ZIP" if present (not required for merge, but used for hover if you like)
    zip_candidates_helper = [c for c in df_helper.columns if c.lower() in ("zip", "zipcode", "postal", "postal code")]
    if zip_candidates_helper:
        helper_zip_col = zip_candidates_helper[0]
        df_helper[helper_zip_col] = df_helper[helper_zip_col].astype(str).str.extract(r"(\d{5})", expand=False).fillna("")
        if helper_zip_col != "ZIP":
            df_helper.rename(columns={helper_zip_col: "ZIP"}, inplace=True)

    # Normalize State in helper
    if "State" in df_helper.columns:
        df_helper["State"] = df_helper["State"].astype(str).str.strip().str.upper()

    # Merge on State
    merged = df_main.merge(df_helper, on="State", how="left", suffixes=("", "_Helper"))

    # If helper provides contact hierarchy, use it to fill blanks in main
    prefer_helper_fields = [
        "WSC_Contact", "WSC_Title", "WSC_SAM", "WSC_RM", "WSC_VP_Sales", "WSC_Director",
        "RBP", "Waudena_NAM", "Waudena_TM", "Waudena_Director", "Email", "Phone"
    ]
    for col in prefer_helper_fields:
        main_has = col in merged.columns
        helper_has = (col + "_Helper") in merged.columns
        if helper_has and main_has:
            merged[col] = merged[col].where(merged[col].notna() & (merged[col].astype(str).str.strip() != ""), merged[col + "_Helper"])
        elif helper_has and not main_has:
            # If main lacks the column entirely, bring in the helper version
            merged[col] = merged[col + "_Helper"]

    # Drop helper-suffixed columns afterward
    merged = merged.loc[:, ~merged.columns.str.endswith("_Helper")]

    # Ensure a single ZIP column is present if at all possible
    if "ZIP" not in merged.columns:
        # Attempt last-ditch creation from any residual zip-like col
        any_zip = [c for c in merged.columns if "zip" in c.lower()]
        if any_zip:
            merged["ZIP"] = merged[any_zip[0]].astype(str).str.extract(r"(\d{5})", expand=False).fillna("")
        else:
            merged["ZIP"] = ""

    # Last cleanup of strings
    for c in merged.columns:
        if merged[c].dtype == "object":
            merged[c] = merged[c].astype(str).str.strip().replace({"nan": "", "None": ""})

    # Helper file timestamp for UI
    try:
        ts = os.path.getmtime(HELPER_PATH)
        helper_msg = f"✅ Helper file loaded • last modified {time.strftime('%b %d, %Y %I:%M %p', time.localtime(ts))}"
    except Exception:
        helper_msg = "✅ Helper file loaded"

    return merged, helper_msg

df, helper_message = load_and_merge()
st.markdown(f"<div style='color:#22c55e;font-weight:600'>{helper_message}</div>", unsafe_allow_html=True)

# ----------------------------
# Reset & sidebar filters
# ----------------------------
if "widget_suffix" not in st.session_state:
    st.session_state["widget_suffix"] = str(uuid.uuid4())

st.sidebar.header("🔍 Filters")
if st.sidebar.button("🔄 Reset Filters"):
    st.session_state.clear()
    st.session_state["widget_suffix"] = str(uuid.uuid4())
    st.cache_data.clear()
    st.toast("✅ Filters reset")
    time.sleep(0.4)
    st.rerun()

sfx = st.session_state.get("widget_suffix", "")

# CUSTOMER
customers = sorted(df["Customer"].dropna().unique()) if "Customer" in df.columns else []
sel_customer = st.sidebar.multiselect("Customer(s)", customers, key=f"cust_{sfx}")

# SAM depends on customer
sam_base = df[df["Customer"].isin(sel_customer)] if sel_customer else df
sams = sorted(sam_base["WSC_SAM"].dropna().unique()) if "WSC_SAM" in df.columns else []
sel_sam = st.sidebar.multiselect("SAM(s)", sams, key=f"sam_{sfx}")

# STATE depends on previous
state_base = sam_base[sam_base["WSC_SAM"].isin(sel_sam)] if sel_sam else sam_base
states = sorted(state_base["State"].dropna().unique()) if "State" in df.columns else []
sel_state = st.sidebar.multiselect("State(s)", states, key=f"state_{sfx}")

# ZIP depends on previous
zip_base = state_base[state_base["State"].isin(sel_state)] if sel_state else state_base
zips = sorted(zip_base["ZIP"].dropna().unique()) if "ZIP" in df.columns else []
sel_zip = st.sidebar.multiselect("ZIP(s)", zips, key=f"zip_{sfx}")

# Free text search
search_text = st.sidebar.text_input("Search any name/title/email/field", key=f"search_{sfx}")

# Stakeholder slicers
st.sidebar.header("👥 Stakeholder Slicers")
stake_cols = [
    "WSC_Contact", "WSC_Title", "WSC_SAM", "WSC_RM", "WSC_VP_Sales", "WSC_Director",
    "RBP", "Waudena_NAM", "Waudena_TM", "Waudena_Director", "Email", "Phone"
]
selected_slicers = []
for col in stake_cols:
    if col in df.columns and st.sidebar.checkbox(col, value=False, key=f"slicer_{col}_{sfx}"):
        selected_slicers.append(col)

# Apply filters
filtered = df.copy()
if sel_customer:
    filtered = filtered[filtered["Customer"].isin(sel_customer)]
if sel_sam and "WSC_SAM" in filtered.columns:
    filtered = filtered[filtered["WSC_SAM"].isin(sel_sam)]
if sel_state:
    filtered = filtered[filtered["State"].isin(sel_state)]
if sel_zip and "ZIP" in filtered.columns:
    filtered = filtered[filtered["ZIP"].isin(sel_zip)]
if search_text:
    patt = re.escape(search_text)
    mask = filtered.apply(lambda r: r.astype(str).str.contains(patt, case=False, na=False)).any(axis=1)
    filtered = filtered[mask]

st.subheader(f"Showing {len(filtered):,} matching records")

# ----------------------------
# Map preparation
# ----------------------------
@st.cache_data
def geocode_zip_series(zip_series: pd.Series) -> pd.DataFrame:
    """Return a dataframe with ZIP, lat, lon for given unique zips."""
    nomi = pgeocode.Nominatim("US")
    uniq = zip_series.dropna().astype(str).unique().tolist()
    if not uniq:
        return pd.DataFrame(columns=["ZIP", "lat", "lon"])
    out = nomi.query_postal_code(uniq)
    if out is None or out.empty:
        return pd.DataFrame(columns=["ZIP", "lat", "lon"])
    out = out.rename(columns={"postal_code": "ZIP", "latitude": "lat", "longitude": "lon"})
    out["ZIP"] = out["ZIP"].astype(str)
    return out[["ZIP", "lat", "lon"]]

# Attach coordinates (recompute only for visible zips)
if "ZIP" in filtered.columns and not filtered.empty:
    geo_lut = geocode_zip_series(filtered["ZIP"])
    geo = filtered.merge(geo_lut, on="ZIP", how="left")
else:
    geo = filtered.copy()
    geo["lat"] = pd.NA
    geo["lon"] = pd.NA

# ----------------------------
# Map Options
# ----------------------------
st.sidebar.header("🗺️ Map Options")
map_view = st.sidebar.radio("Map View", ["Pin Map", "Heatmap"], key=f"map_{sfx}")

has_coords = (geo[["lat", "lon"]].dropna().shape[0] > 0) if not geo.empty else False
if has_coords:
    geo_nonan = geo.dropna(subset=["lat", "lon"])
    hover_data = {}
    for col in ["State", "ZIP", "WSC_SAM", "WSC_Contact", "WSC_Title", "Phone", "Email"]:
        if col in geo_nonan.columns:
            hover_data[col] = True

    if map_view == "Pin Map":
        fig = px.scatter_mapbox(
            geo_nonan,
            lat="lat", lon="lon",
            hover_name="Customer" if "Customer" in geo_nonan.columns else None,
            hover_data=hover_data,
            color="Customer" if "Customer" in geo_nonan.columns else None,
            zoom=3, height=560
        )
    else:
        fig = px.density_mapbox(
            geo_nonan,
            lat="lat", lon="lon",
            radius=12,
            zoom=3, height=560
        )
    fig.update_layout(mapbox_style="carto-positron", margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No mappable locations for current filters.")

# ----------------------------
# Table Display Options
# ----------------------------
st.sidebar.header("📄 Table Display Options")

all_cols = filtered.columns.tolist()
smart_defaults = [
    "Customer", "WSC_SAM", "State", "ZIP",
    "WSC_VP_Sales", "WSC_RM", "Email", "Phone"
]
selected_cols = st.sidebar.multiselect(
    "Select columns to include:",
    options=all_cols,
    default=[c for c in smart_defaults if c in all_cols],
    key=f"cols_{sfx}"
)

# Extended toggle
st.sidebar.divider()
show_extended = st.sidebar.checkbox("🧩 Show Extended Fields", value=False, key=f"ext_{sfx}")
extended_fields = [
    "WSC_Title", "WSC_Contact", "WSC_Director",
    "RBP", "Waudena_NAM", "Waudena_TM", "Waudena_Director"
]
final_cols = list(selected_cols)
if show_extended:
    for c in extended_fields:
        if c in all_cols and c not in final_cols:
            final_cols.append(c)

# Always include slicer-chosen stakeholder columns
for c in selected_slicers:
    if c in all_cols and c not in final_cols:
        final_cols.append(c)

# Results table + export
st.subheader("📋 Filtered Results")
if final_cols:
    table = filtered[final_cols] if set(final_cols).issubset(filtered.columns) else filtered
    st.dataframe(table, use_container_width=True)
    csv_bytes = table.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Export Filtered Data (CSV)",
        data=csv_bytes,
        file_name="Filtered_Accounts.csv",
        mime="text/csv"
    )
else:
    st.info("Select one or more columns in **Table Display Options** to display results.")

# ----------------------------
# Auto-collapse selects after pick
# ----------------------------
st.markdown("""
<script>
const selects = document.querySelectorAll('div[data-baseweb="select"]');
selects.forEach(sel => sel.addEventListener('change', ()=>{document.activeElement.blur();}));
</script>
""", unsafe_allow_html=True)
