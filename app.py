import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date, timedelta
from invoice_generator import generate_invoice_pdf

# --- 1. SETUP & CONNECTION ---
st.set_page_config(page_title="Consultant Tracker", layout="wide")

@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- 2. DATA FETCHING FUNCTIONS ---

def get_active_projects():
    response = supabase.table("projects").select("*, clients(name)").eq("active", True).execute()
    return pd.DataFrame(response.data)

def get_time_usage():
    response = supabase.table("time_entries").select("project_id, hours, billed").execute()
    df = pd.DataFrame(response.data)
    if df.empty:
        return pd.DataFrame(columns=["project_id", "total_hours", "unbilled_hours"])
    df["hours"] = pd.to_numeric(df["hours"])
    total_usage = df.groupby("project_id")["hours"].sum().reset_index().rename(columns={"hours": "total_hours"})
    unbilled_df = df[df["billed"] == False]
    unbilled_usage = unbilled_df.groupby("project_id")["hours"].sum().reset_index().rename(columns={"hours": "unbilled_hours"}) if not unbilled_df.empty else pd.DataFrame(columns=["project_id", "unbilled_hours"])
    usage = pd.merge(total_usage, unbilled_usage, on="project_id", how="left")
    usage["unbilled_hours"] = usage["unbilled_hours"].fillna(0.0)
    return usage

def fetch_pos_for_project(project_id):
    response = supabase.table("purchase_orders").select("id, po_number").eq("project_id", project_id).execute()
    return response.data

def submit_time_entry(project_id, po_id, date_worked, description, hours):
    data = {"project_id": project_id, "po_id": po_id, "date_worked": str(date_worked), "description": description.strip(), "hours": hours, "billed": False}
    try:
        supabase.table("time_entries").insert(data).execute()
        st.success(f"✅ Logged {hours} hours on {date_worked}")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Database Error: {e}")

def fetch_invoice_preview(project_id, start_date, end_date):
    # Added 'id' to the select so we can track which rows to update later
    response = supabase.table("time_entries")\
        .select("id, date_worked, description, hours, purchase_orders(po_number)")\
        .eq("project_id", project_id)\
        .eq("billed", False)\
        .gte("date_worked", str(start_date))\
        .lte("date_worked", str(end_date))\
        .order("date_worked", desc=False)\
        .execute()
    return pd.DataFrame(response.data)

def mark_entries_as_billed(entry_ids, invoice_ref):
    """Updates the billed status for ALL selected entries in one batch request."""
    try:
        # We use .in_() to match any ID in the list
        supabase.table("time_entries")\
            .update({"billed": True, "invoice_ref": invoice_ref})\
            .in_("id", entry_ids)\
            .execute()
        return True
    except Exception as e:
        st.error(f"Error updating billing status: {e}")
        return False

# --- 3. MAIN UI LAYOUT ---
st.title("Consultant Time & Budget Tracker")

tab_entry, tab_dashboard, tab_invoice = st.tabs(["📝 Log Time", "🚀 Dashboard", "📄 Invoices"])

# --- TAB 1: DATA ENTRY ---
with tab_entry:
    st.header("Day Sheet")
    projects_df = get_active_projects()
    if not projects_df.empty:
        project_options = {f"{row['clients']['name']} | {row['name']}": row['id'] for index, row in projects_df.iterrows()}
        selected_project_label = st.selectbox("Select Project", options=list(project_options.keys()))
        selected_project_id = project_options[selected_project_label]
        pos = fetch_pos_for_project(selected_project_id)
        po_options = {p['po_number']: p['id'] for p in pos} if pos else {"N/A": None}
        if pos: po_options["General / No PO"] = None

        with st.form("time_entry_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                date_input = st.date_input("Date", value=date.today())
                selected_po_label = st.selectbox("Purchase Order (PO)", options=list(po_options.keys()))
                selected_po_id = po_options[selected_po_label]
            with col2:
                hours_input = st.number_input("Hours Worked", min_value=0.0, step=0.25, format="%.2f")
            desc_input = st.text_input("Description", placeholder="e.g., Q3 Strategic Planning Meeting")
            submitted = st.form_submit_button("Submit Time Entry")
            if submitted:
                if hours_input <= 0: st.error("Validation Error: Hours must be greater than 0.")
                elif not desc_input.strip(): st.error("Validation Error: Please provide a description.")
                else: submit_time_entry(selected_project_id, selected_po_id, date_input, desc_input, hours_input)

# --- TAB 2: DASHBOARD ---
with tab_dashboard:
    st.header("Project Overview")
    projects_df = get_active_projects()
    usage_df = get_time_usage()
    if not projects_df.empty:
        dashboard_data = pd.merge(projects_df, usage_df, left_on="id", right_on="project_id", how="left")
        dashboard_data["total_hours"] = dashboard_data["total_hours"].fillna(0.0)
        dashboard_data["days_used"] = dashboard_data["total_hours"] / 8.0
        dashboard_data["budget_remaining"] = dashboard_data["loa_budget_days"] - dashboard_data["days_used"]
        dashboard_data["client_name"] = dashboard_data["clients"].apply(lambda x: x.get("name", "Unknown") if isinstance(x, dict) else "Unknown")

        for index, row in dashboard_data.iterrows():
            st.subheader(f"{row['client_name']} | {row['name']}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Budget Cap", f"{row['loa_budget_days']:.2f} Days")
            c2.metric("Days Used", f"{row['days_used']:.2f} Days")
            c3.metric("Days Remaining", f"{row['budget_remaining']:.2f} Days")
            st.progress(max(0.0, min(1.0, row['days_used'] / row['loa_budget_days'])))
            st.markdown("---")

# --- TAB 3: INVOICE GENERATOR ---
with tab_invoice:
    st.header("Generate Invoice")
    col1, col2 = st.columns(2)
    with col1:
        inv_projects_df = get_active_projects()
        inv_project_options = {f"{row['clients']['name']} | {row['name']}": row['id'] for index, row in inv_projects_df.iterrows()}
        inv_selected_label = st.selectbox("Select Project for Invoice", options=list(inv_project_options.keys()))
        inv_project_id = inv_project_options[inv_selected_label]
        qb_invoice_num = st.text_input("QuickBooks Invoice #", placeholder="e.g. 1099")
    with col2:
        date_range = st.date_input("Select Date Range", value=(date.today().replace(day=1), date.today()))

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        preview_df = fetch_invoice_preview(inv_project_id, start_date, end_date)
        
        if not preview_df.empty:
            preview_df["PO"] = preview_df["purchase_orders"].apply(lambda x: x.get("po_number", "General") if isinstance(x, dict) else "General")
            st.dataframe(preview_df[["date_worked", "description", "PO", "hours"]], width="stretch")
            
            total_inv_hours = preview_df["hours"].sum()
            st.metric("Total Invoice Days", f"{total_inv_hours / 8.0:.4f} Days")
            
            # --- TASK 12, 13 & 14: PDF GENERATION ---
            st.write("---")
            if st.button("Generate Invoice PDF"):
                if not qb_invoice_num:
                    st.error("Please enter a QuickBooks Invoice # first.")
                else:
                    # 1. Fetch Project Details for the Math
                    proj_data = inv_projects_df[inv_projects_df['id'] == inv_project_id].iloc[0]
                    
                    # 2. Calculate History (Prior Billed Days)
                    history_response = supabase.table("time_entries") \
                        .select("hours") \
                        .eq("project_id", inv_project_id) \
                        .eq("billed", True) \
                        .execute()
                    
                    prior_hours = sum([item['hours'] for item in history_response.data])
                    prior_days = prior_hours / 8.0

                    # 3. Prepare Line Items (Task 14)
                    # Convert the preview dataframe to a list of dictionaries
                    line_items = preview_df.to_dict('records')
                    
                    # 4. Generate PDF
                    pdf_bytes = generate_invoice_pdf(
                        project_name=inv_selected_label.split(" | ")[1], 
                        invoice_num=qb_invoice_num, 
                        start_date=start_date, 
                        end_date=end_date,
                        loa_start=proj_data['loa_start'],
                        loa_end=proj_data['loa_end'],
                        loa_budget=float(proj_data['loa_budget_days']),
                        daily_rate=float(proj_data['daily_rate']),
                        current_hours=total_inv_hours,
                        prior_billed_days=prior_days,
                        # Pass the detailed entries
                        line_items=line_items
                    )
                    
                    st.download_button(
                        label="⬇️ Download PDF",
                        data=pdf_bytes,
                        file_name=f"Invoice_{qb_invoice_num}.pdf",
                        mime="application/pdf"
                    )
                    st.success("PDF Generated! Click the download button above.")

            # --- TASK 11: FINALIZE BUTTON ---
            st.write("---")
            st.warning("⚠️ Clicking below will remove these entries from future invoices.")
            if st.button("Finalize & Mark as Billed"):
                if not qb_invoice_num:
                    st.error("Please enter a QuickBooks Invoice # before finalizing.")
                else:
                    success = mark_entries_as_billed(preview_df["id"].tolist(), qb_invoice_num)
                    if success:
                        st.success(f"Invoice {qb_invoice_num} finalized! entries locked.")
                        st.cache_data.clear()
        else:
            st.info("No unbilled entries found for this range.")