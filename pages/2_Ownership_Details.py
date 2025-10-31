import streamlit as st
import pandas as pd

st.title("🏛️ Ownership Details — Customer & WSC Contacts")

# ----------------------------
# Retrieve active filters
# ----------------------------
filters = st.session_state.get("filters", {})
sel_customer = filters.get("Customer", [])
sel_sam = filters.get("SAM", [])
sel_state = filters.get("State", [])
sel_zip = filters.get("ZIP", [])

st.subheader("🎯 Active Search Criteria")
criteria_data = {
    "Filter Type": ["Customer", "SAM", "State", "ZIP"],
    "Selected Value": [
        ", ".join(sel_customer) or "All",
        ", ".join(sel_sam) or "All",
        ", ".join(sel_state) or "All",
        ", ".join(sel_zip) or "All",
    ],
}
st.table(pd.DataFrame(criteria_data))

# ----------------------------
# Load merged data
# ----------------------------
MAIN_PATH = "Strategic_Account_Ownership_Master.xlsx"
HELPER_PATH = "State_Contacts.xlsx"

@st.cache_data(ttl=60)
def load_data():
    df_main = pd.read_excel(MAIN_PATH, sheet_name="Database")
    df_helper = pd.read_excel(HELPER_PATH, sheet_name="Contacts")
    df_helper = df_helper.loc[:, ~df_helper.columns.astype(str).str.startswith("Unnamed")]
    df_main.columns = df_main.columns.str.strip()
    df_helper.columns = df_helper.columns.str.strip()
    df_main["State"] = df_main["State"].astype(str).str.strip().str.upper()
    df_helper["State"] = df_helper["State"].astype(str).str.strip().str.upper()
    df = df_main.merge(df_helper, on="State", how="left", suffixes=("", "_Helper"))
    return df

df = load_data()

# Apply same filters
filtered = df.copy()
if sel_customer:
    filtered = filtered[filtered["Customer"].isin(sel_customer)]
if sel_sam and "WSC_SAM" in filtered.columns:
    filtered = filtered[filtered["WSC_SAM"].isin(sel_sam)]
if sel_state:
    filtered = filtered[filtered["State"].isin(sel_state)]
if sel_zip and "ZIP" in filtered.columns:
    filtered = filtered[filtered["ZIP"].isin(sel_zip)]

# ----------------------------
# Sidebar: Column display controls
# ----------------------------
st.sidebar.header("📋 Display Options")

all_cols = sorted(filtered.columns.tolist())

cust_cols_default = [c for c in ["Customer", "State", "City", "ZIP", "WSC_SAM", "Email", "Phone"] if c in all_cols]
cust_cols = st.sidebar.multiselect(
    "Customer Contact Fields",
    options=all_cols,
    default=cust_cols_default,
    key="cust_fields",
    help="Select which columns to show in the Customer Contacts table.",
)

wsc_cols_default = [c for c in ["State", "WSC_Contact", "WSC_Title", "Siding_Specialist",
                                "WSC_SAM", "WSC_RM", "WSC_VP_Sales", "Email", "Phone"] if c in all_cols]
wsc_cols = st.sidebar.multiselect(
    "WSC Ownership Fields",
    options=all_cols,
    default=wsc_cols_default,
    key="wsc_fields",
    help="Select which columns to show in the WSC Ownership table.",
)

# ----------------------------
# Results
# ----------------------------
st.divider()
st.subheader("🏢 Customer Contacts")
if cust_cols:
    st.dataframe(filtered[cust_cols], use_container_width=True)
else:
    st.info("Select one or more columns in the sidebar to view Customer Contacts.")

st.divider()
st.subheader("🏛️ WSC Ownership Contacts")
if wsc_cols:
    st.dataframe(filtered[wsc_cols].drop_duplicates(), use_container_width=True)
else:
    st.info("Select one or more columns in the sidebar to view WSC Ownership Contacts.")

# ----------------------------
# Export Options
# ----------------------------
st.divider()
st.subheader("⬇️ Export Ownership Data")

col1, col2 = st.columns(2)

if not filtered.empty:
    with col1:
        if cust_cols:
            csv_customers = filtered[cust_cols].to_csv(index=False).encode("utf-8")
            st.download_button(
                "💾 Export Customer Contacts (CSV)",
                csv_customers,
                f"Customer_Contacts_{pd.Timestamp.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    with col2:
        if wsc_cols:
            csv_wsc = filtered[wsc_cols].drop_duplicates().to_csv(index=False).encode("utf-8")
            st.download_button(
                "💾 Export WSC Ownership Contacts (CSV)",
                csv_wsc,
                f"WSC_Ownership_Contacts_{pd.Timestamp.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
else:
    st.info("No data available for export based on current filters.")

st.caption("Tables automatically reflect filters and column selections from this page.")
