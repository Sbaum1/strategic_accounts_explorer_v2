import streamlit as st
import pandas as pd

st.title("🏛️ Ownership Details — Customer & WSC Contacts")

# ----------------------------
# Retrieve filters from Page 1
# ----------------------------
filters = st.session_state.get("filters", {})
sel_customer = filters.get("Customer", [])
sel_sam = filters.get("SAM", [])
sel_state = filters.get("State", [])
sel_zip = filters.get("ZIP", [])

# Display current filters
st.subheader("🎯 Active Search Criteria")
criteria = pd.DataFrame({
    "Filter Type": ["Customer", "SAM", "State", "ZIP"],
    "Selected Value": [
        ", ".join(sel_customer) or "All",
        ", ".join(sel_sam) or "All",
        ", ".join(sel_state) or "All",
        ", ".join(sel_zip) or "All"
    ]
})
st.table(criteria)

# ----------------------------
# Load source data
# ----------------------------
MAIN_PATH = "Strategic_Account_Ownership_Master.xlsx"
HELPER_PATH = "State_Contacts.xlsx"

@st.cache_data(ttl=60)
def load_data():
    df_cust = pd.read_excel(MAIN_PATH, sheet_name="Database")
    df_wsc = pd.read_excel(HELPER_PATH, sheet_name="Contacts")

    # Clean
    df_cust.columns = df_cust.columns.str.strip()
    df_wsc.columns = df_wsc.columns.str.strip()
    df_cust["State"] = df_cust["State"].astype(str).str.strip().str.upper()
    df_wsc["State"] = df_wsc["State"].astype(str).str.strip().str.upper()

    return df_cust, df_wsc

df_cust, df_wsc = load_data()

# Apply filters (customers)
filtered_cust = df_cust.copy()
if sel_customer:
    filtered_cust = filtered_cust[filtered_cust["Customer"].isin(sel_customer)]
if sel_sam and "WSC_SAM" in filtered_cust.columns:
    filtered_cust = filtered_cust[filtered_cust["WSC_SAM"].isin(sel_sam)]
if sel_state:
    filtered_cust = filtered_cust[filtered_cust["State"].isin(sel_state)]
if sel_zip and "ZIP" in filtered_cust.columns:
    filtered_cust = filtered_cust[filtered_cust["ZIP"].isin(sel_zip)]

# Filter WSC table based on selected states
filtered_wsc = df_wsc.copy()
if sel_state:
    filtered_wsc = filtered_wsc[filtered_wsc["State"].isin(sel_state)]

# ----------------------------
# Sidebar: Column selection
# ----------------------------
st.sidebar.header("📋 Display Options")

cust_cols_default = [c for c in ["Customer", "State", "City", "ZIP", "WSC_SAM", "Email", "Phone"] if c in df_cust.columns]
cust_cols = st.sidebar.multiselect(
    "Customer Contact Fields",
    options=df_cust.columns.tolist(),
    default=cust_cols_default,
    key="cust_fields",
)

wsc_cols_default = [c for c in ["State", "WSC_Contact", "WSC_Title", "Siding_Specialist",
                                "WSC_SAM", "WSC_RM", "WSC_VP_Sales", "Email", "Phone"] if c in df_wsc.columns]
wsc_cols = st.sidebar.multiselect(
    "WSC Ownership Fields",
    options=df_wsc.columns.tolist(),
    default=wsc_cols_default,
    key="wsc_fields",
)

# ----------------------------
# Display tables
# ----------------------------
st.divider()
st.subheader("🏢 Customer Contacts")
if not filtered_cust.empty and cust_cols:
    st.dataframe(filtered_cust[cust_cols], use_container_width=True)
else:
    st.info("No customer data or no columns selected.")

st.divider()
st.subheader("🏛️ WSC Ownership Contacts")
if not filtered_wsc.empty and wsc_cols:
    st.dataframe(filtered_wsc[wsc_cols].drop_duplicates(), use_container_width=True)
else:
    st.info("No WSC data or no columns selected.")

# ----------------------------
# Export Options
# ----------------------------
st.divider()
st.subheader("⬇️ Export Ownership Data")

if not filtered_cust.empty:
    st.download_button(
        "💾 Export Customer Contacts (CSV)",
        filtered_cust[cust_cols].to_csv(index=False).encode("utf-8"),
        "Customer_Contacts.csv",
        mime="text/csv"
    )
if not filtered_wsc.empty:
    st.download_button(
        "💾 Export WSC Ownership Contacts (CSV)",
        filtered_wsc[wsc_cols].drop_duplicates().to_csv(index=False).encode("utf-8"),
        "WSC_Ownership_Contacts.csv",
        mime="text/csv"
    )

st.caption("Customer and WSC tables are filtered dynamically from their respective Excel sheets.")
