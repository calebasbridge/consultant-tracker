import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date, timedelta
from invoice_generator import generate_invoice_pdf

# --- 1. SETUP & CONNECTION ---
st.set_page_config(page_title="Consultant Tracker", layout="wide", page_icon="💼")

@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase: Client = init_connection()

# --- 2. DATA FETCHING FUNCTIONS ---

def get_active_projects():
    """Fetch active projects with client names."""
    response = supabase.table("projects").select("*, clients(name)").eq("active", True).execute()
    return pd.DataFrame(response.data)

def get_all_clients():
    """Fetch all clients for the Project Creation dropdown."""
    response = supabase.table("clients").select("*").order("name").execute()
    return pd.DataFrame(response.data)

def get_time_usage():
    """Calculate billed vs unbilled usage for the dashboard."""
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

def get_entries_by_date(target_date):
    """Fetches entries for a specific date (Daily Snapshot)."""
    # Nested select to handle the Client -> Project -> Entry relationship
    response = supabase.table("time_entries")\
        .select("*, projects(name, clients(name)), purchase_orders(po_number)")\
        .eq("date_worked", str(target_date))\
        .execute()
    
    df = pd.DataFrame(response.data)
    if not df.empty:
        df["Project"] = df["projects"].apply(lambda x: x.get("name") if x else "")
        df["Client"] = df["projects"].apply(lambda x: x.get("clients", {}).get("name") if x and x.get("clients") else "")
        df["PO"] = df["purchase_orders"].apply(lambda x: x.get("po_number") if x else "N/A")
        return df[["Client", "Project", "PO", "description", "hours"]]
    return pd.DataFrame()

def get_revenue_projection(start_date, end_date):
    """Fetches unbilled time + rates for forecasting."""
    response = supabase.table("time_entries")\
        .select("hours, date_worked, projects(name, daily_rate)")\
        .eq("billed", False)\
        .gte("date_worked", str(start_date))\
        .lte("date_worked", str(end_date))\
        .execute()
    
    data = []
    for row in response.data:
        proj = row.get("projects", {})
        if proj:
            p_name = proj.get("name", "Unknown")
            p_rate = float(proj.get("daily_rate", 0))
            hours = float(row.get("hours", 0))
            hourly_rate = p_rate / 8.0
            amount = hours * hourly_rate
            data.append({
                "Project": p_name,
                "Date": row["date_worked"],
                "Hours": hours,
                "Rate": hourly_rate,
                "Amount": amount
            })
    return pd.DataFrame(data)

def fetch_invoice_preview(project_id, start_date, end_date):
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
    try:
        supabase.table("time_entries")\
            .update({"billed": True, "invoice_ref": invoice_ref})\
            .in_("id", entry_ids)\
            .execute()
        return True
    except Exception as e:
        st.error(f"Error updating billing status: {e}")
        return False

# --- MANAGERIAL FUNCTIONS ---
def create_project(client_id, name, start, end, budget, rate):
    data = {
        "client_id": client_id, "name": name, "loa_start": str(start),
        "loa_end": str(end), "loa_budget_days": budget, "daily_rate": rate, "active": True
    }
    try:
        supabase.table("projects").insert(data).execute()
        st.success(f"✅ Project '{name}' created successfully!")
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error creating project: {e}")
        return False

def update_project(project_id, updates):
    try:
        supabase.table("projects").update(updates).eq("id", project_id).execute()
        st.success("✅ Project updated successfully!")
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error updating project: {e}")
        return False

# --- 3. MAIN UI LAYOUT ---
st.title("Consultant Time & Budget Tracker")

tab_entry, tab_dashboard, tab_invoice, tab_finance, tab_manage = st.tabs([
    "📝 Log Time", "🚀 Dashboard", "📄 Invoices", "💰 Forecasting", "🛠️ Manage"
])

# --- TAB 1: DATA ENTRY ---
with tab_entry:
    st.header("Day Sheet")
    projects_df = get_active_projects()
    
    # REVISION: Reactive Date Picker
    c1, c2 = st.columns([1, 2])
    with c1:
        date_input = st.date_input("Select Date", value=date.today())
    
    # REVISION: Daily Snapshot with "width" fixed
    daily_df = get_entries_by_date(date_input)
    if not daily_df.empty:
        total_day_hours = daily_df["hours"].sum()
        st.info(f"📅 **Total Logged for {date_input.strftime('%b %d')}:** {total_day_hours:.2f} Hours ({total_day_hours/8.0:.2f} Days)")
        st.dataframe(daily_df.style.format({"hours": "{:.2f}"}), width="stretch", hide_index=True)
    else:
        st.caption(f"No entries logged for {date_input.strftime('%b %d')} yet.")
    
    st.write("---")
    
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
    
    view_mode = st.radio("Display Units:", ["Days", "Hours", "Both"], horizontal=True)
    st.write("---")

    projects_df = get_active_projects()
    usage_df = get_time_usage()
    
    if not projects_df.empty:
        dashboard_data = pd.merge(projects_df, usage_df, left_on="id", right_on="project_id", how="left")
        dashboard_data["total_hours"] = dashboard_data["total_hours"].fillna(0.0)
        
        dashboard_data["days_used"] = dashboard_data["total_hours"] / 8.0
        dashboard_data["budget_remaining_days"] = dashboard_data["loa_budget_days"] - dashboard_data["days_used"]
        dashboard_data["budget_remaining_hours"] = dashboard_data["budget_remaining_days"] * 8.0
        dashboard_data["budget_total_hours"] = dashboard_data["loa_budget_days"] * 8.0
        
        dashboard_data["client_name"] = dashboard_data["clients"].apply(lambda x: x.get("name", "Unknown") if isinstance(x, dict) else "Unknown")

        for index, row in dashboard_data.iterrows():
            st.subheader(f"{row['client_name']} | {row['name']}")
            
            if view_mode == "Days":
                cap_label = f"{row['loa_budget_days']:.2f} Days"
                used_label = f"{row['days_used']:.2f} Days"
                rem_label = f"{row['budget_remaining_days']:.2f} Days"
            elif view_mode == "Hours":
                cap_label = f"{row['budget_total_hours']:.2f} Hours"
                used_label = f"{row['total_hours']:.2f} Hours"
                rem_label = f"{row['budget_remaining_hours']:.2f} Hours"
            else: # Both
                cap_label = f"{row['loa_budget_days']:.2f} D / {row['budget_total_hours']:.1f} H"
                used_label = f"{row['days_used']:.2f} D / {row['total_hours']:.1f} H"
                rem_label = f"{row['budget_remaining_days']:.2f} D / {row['budget_remaining_hours']:.1f} H"

            c1, c2, c3 = st.columns(3)
            c1.metric("Budget Cap", cap_label)
            c2.metric("Days Used", used_label)
            c3.metric("Remaining", rem_label)
            
            if row['loa_budget_days'] > 0:
                st.progress(max(0.0, min(1.0, row['days_used'] / row['loa_budget_days'])))
            else:
                st.warning("Budget is 0 days.")
            st.markdown("---")
    else:
        st.info("No active projects found.")

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
            
            # REVISION: Rounded to 2 decimal places
            st.metric("Total Invoice Days", f"{total_inv_hours / 8.0:.2f} Days")
            
            st.write("---")
            if st.button("Generate Invoice PDF"):
                if not qb_invoice_num:
                    st.error("Please enter a QuickBooks Invoice # first.")
                else:
                    proj_data = inv_projects_df[inv_projects_df['id'] == inv_project_id].iloc[0]
                    
                    history_response = supabase.table("time_entries") \
                        .select("hours") \
                        .eq("project_id", inv_project_id) \
                        .eq("billed", True) \
                        .execute()
                    
                    prior_hours = sum([item['hours'] for item in history_response.data])
                    prior_days = prior_hours / 8.0
                    
                    line_items = preview_df.to_dict('records')
                    
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
                        line_items=line_items
                    )
                    
                    st.download_button(
                        label="⬇️ Download PDF",
                        data=pdf_bytes,
                        file_name=f"Invoice_{qb_invoice_num}.pdf",
                        mime="application/pdf"
                    )
                    st.success("PDF Generated! Click the download button above.")

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

# --- TAB 4: FINANCIAL FORECASTING ---
with tab_finance:
    st.header("Cash Flow & Billing Planner")
    
    c1, c2 = st.columns(2)
    with c1:
        today = date.today()
        first = today.replace(day=1)
        forecast_range = st.date_input("Billing Period", value=(first, today), key="finance_range")
    
    if isinstance(forecast_range, tuple) and len(forecast_range) == 2:
        f_start, f_end = forecast_range
        rev_df = get_revenue_projection(f_start, f_end)
        
        if not rev_df.empty:
            all_projects = rev_df["Project"].unique().tolist()
            selected_projects = st.multiselect("Include Projects in Forecast", options=all_projects, default=all_projects)
            
            filtered_df = rev_df[rev_df["Project"].isin(selected_projects)]
            
            if not filtered_df.empty:
                total_rev = filtered_df["Amount"].sum()
                total_hours = filtered_df["Hours"].sum()
                
                st.markdown("### Projected Revenue")
                m1, m2 = st.columns(2)
                m1.metric("Total Billable Amount", f"${total_rev:,.2f}")
                m2.metric("Billable Hours", f"{total_hours:.2f}")
                
                st.markdown("#### Breakdown by Project")
                summary = filtered_df.groupby("Project")[["Hours", "Amount"]].sum().reset_index()
                summary["Amount"] = summary["Amount"].apply(lambda x: f"${x:,.2f}") 
                # REVISION: Fixed deprecated parameter
                st.dataframe(summary, width="stretch")
            else:
                st.warning("No projects selected.")
            
        else:
            st.info("No unbilled time found in this period.")

# --- TAB 5: MANAGE PROJECTS ---
with tab_manage:
    st.header("Project Administration")
    
    clients_df = get_all_clients()
    # Fetch all projects (including archived) for editing
    all_projects_response = supabase.table("projects").select("*, clients(name)").order("name").execute()
    all_projects_df = pd.DataFrame(all_projects_response.data)

    tab_create, tab_edit = st.tabs(["New Project", "Edit / Archive"])

    # SUB-TAB: CREATE
    with tab_create:
        st.subheader("Create New Project")
        if not clients_df.empty:
            with st.form("create_project_form"):
                client_map = {row['name']: row['id'] for i, row in clients_df.iterrows()}
                c_name = st.selectbox("Client", options=list(client_map.keys()))
                p_name = st.text_input("Project Name", placeholder="e.g. 25 FY Leadership Ops")
                
                c1, c2 = st.columns(2)
                p_start = c1.date_input("LOA Start", value=date.today())
                p_end = c2.date_input("LOA End", value=date.today() + timedelta(days=365))
                
                c3, c4 = st.columns(2)
                p_budget = c3.number_input("Budget (Days)", min_value=0.0, step=0.5)
                p_rate = c4.number_input("Daily Rate ($)", min_value=0.0, step=50.0)
                
                if st.form_submit_button("Create Project"):
                    if not p_name:
                        st.error("Project Name is required.")
                    else:
                        create_project(client_map[c_name], p_name, p_start, p_end, p_budget, p_rate)
        else:
            st.warning("No clients found. Please add clients in Supabase first.")

    # SUB-TAB: EDIT
    with tab_edit:
        st.subheader("Edit or Archive Project")
        if not all_projects_df.empty:
            # Dropdown to select project
            all_projects_df["display_name"] = all_projects_df.apply(
                lambda x: f"{'🔴' if not x['active'] else '🟢'} {x['clients']['name']} | {x['name']}", axis=1
            )
            proj_map = {row['display_name']: row for i, row in all_projects_df.iterrows()}
            
            selected_proj_label = st.selectbox("Select Project to Edit", options=list(proj_map.keys()))
            proj_data = proj_map[selected_proj_label]
            
            # Edit Form
            with st.form("edit_project_form"):
                new_name = st.text_input("Project Name", value=proj_data['name'])
                
                c1, c2 = st.columns(2)
                # Parse dates safely
                d_start = date.fromisoformat(proj_data['loa_start'])
                d_end = date.fromisoformat(proj_data['loa_end'])
                
                new_start = c1.date_input("LOA Start", value=d_start)
                new_end = c2.date_input("LOA End", value=d_end)
                
                c3, c4 = st.columns(2)
                new_budget = c3.number_input("Budget (Days)", value=float(proj_data['loa_budget_days']), step=0.5)
                new_rate = c4.number_input("Daily Rate ($)", value=float(proj_data['daily_rate']), step=50.0)
                
                # STATUS TOGGLE
                st.markdown("---")
                is_active = st.checkbox("Project is Active", value=proj_data['active'], help="Uncheck to Archive this project (Remove from menus)")
                
                if st.form_submit_button("Update Project"):
                    updates = {
                        "name": new_name,
                        "loa_start": str(new_start),
                        "loa_end": str(new_end),
                        "loa_budget_days": new_budget,
                        "daily_rate": new_rate,
                        "active": is_active
                    }
                    update_project(proj_data['id'], updates)
        else:
            st.info("No projects found.")