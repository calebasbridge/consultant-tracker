# invoice_generator.py
from fpdf import FPDF
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

class InvoicePDF(FPDF):
    def __init__(self, project_name, invoice_number, date_range):
        super().__init__()
        self.project_name = project_name
        self.invoice_number = invoice_number
        self.date_range = date_range
        
    def header(self):
        # --- Logo & Company Name ---
        self.set_font('Helvetica', 'B', 16)
        self.cell(0, 10, 'Canto Chao, Inc.', ln=True, align='L')
        
        # --- Company Contact Info ---
        self.set_font('Helvetica', '', 10)
        self.cell(0, 5, '30 N. Gould St., Suite 23878', ln=True, align='L')
        self.cell(0, 5, 'Sheridan, WY 82801', ln=True, align='L')
        self.ln(10)
        
        # --- Invoice Metadata ---
        top_y = self.get_y()
        self.set_font('Helvetica', 'B', 12)
        self.cell(100, 6, f"Project: {self.project_name}", ln=True)
        
        self.set_xy(120, top_y)
        self.set_font('Helvetica', 'B', 12)
        self.cell(70, 6, "INVOICE", ln=True, align='R')
        
        self.set_x(120)
        self.set_font('Helvetica', '', 10)
        self.cell(30, 6, "Invoice #:", align='L')
        self.cell(40, 6, self.invoice_number, align='R', ln=True)
        
        self.set_x(120)
        self.cell(30, 6, "Period:", align='L')
        self.cell(40, 6, self.date_range, align='R', ln=True)
        
        self.set_x(120)
        self.cell(30, 6, "Date:", align='L')
        self.cell(40, 6, datetime.today().strftime('%Y-%m-%d'), align='R', ln=True)
        
        self.ln(10)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')

    def add_financial_tables(self, loa_start, loa_end, loa_budget_days, daily_rate, 
                             days_used_this_inv, prior_days_used):
        # --- MATH FIX: Use Decimal for Financial Precision ---
        d_daily = Decimal(str(daily_rate))
        # Quantize ensures we round 90.625 -> 90.63 (ROUND_HALF_UP)
        d_hourly = (d_daily / Decimal(8)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Recalculate totals using the corrected hourly rate
        total_days_used = prior_days_used + days_used_this_inv
        remaining_days = loa_budget_days - total_days_used
        
        # Total Amount = Days * 8 * Rounded Hourly Rate
        total_amount_due = Decimal(days_used_this_inv) * Decimal(8) * d_hourly
        
        # --- TABLE 1: CONTRACT STATUS ---
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, 6, "Contract Status", ln=True)
        self.set_font('Helvetica', '', 9)
        
        # Headers
        self.set_fill_color(240, 240, 240)
        self.cell(35, 6, "LOA Begin", 1, 0, 'C', True)
        self.cell(35, 6, "LOA End", 1, 0, 'C', True)
        self.cell(40, 6, "Total LOA Days", 1, 0, 'C', True)
        self.cell(40, 6, "Daily Rate", 1, 0, 'C', True)
        self.cell(40, 6, "Hourly Rate", 1, 1, 'C', True) 
        
        # Data
        self.cell(35, 6, str(loa_start), 1, 0, 'C')
        self.cell(35, 6, str(loa_end), 1, 0, 'C')
        self.cell(40, 6, f"{loa_budget_days:.2f}", 1, 0, 'C')
        self.cell(40, 6, f"${daily_rate:,.2f}", 1, 0, 'C')
        self.cell(40, 6, f"${d_hourly:,.2f}", 1, 1, 'C') # Display corrected rate
        self.ln(5)
        
        # --- TABLE 2: BUDGET SUMMARY ---
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, 6, "Budget Summary (This Invoice)", ln=True)
        self.set_font('Helvetica', '', 9)
        
        # Headers
        self.cell(50, 6, "Timeframe", 1, 0, 'C', True)
        self.cell(35, 6, "Days Used", 1, 0, 'C', True)
        self.cell(35, 6, "Days Remaining", 1, 0, 'C', True)
        self.cell(35, 6, "Total Amount", 1, 0, 'C', True)
        self.cell(35, 6, "Total Hours", 1, 1, 'C', True)
        
        # Data
        self.cell(50, 6, self.date_range, 1, 0, 'C')
        self.cell(35, 6, f"{days_used_this_inv:.4f}", 1, 0, 'C')
        self.set_font('Helvetica', 'B' if remaining_days < 1.0 else '', 9)
        self.cell(35, 6, f"{remaining_days:.4f}", 1, 0, 'C')
        self.set_font('Helvetica', '', 9)
        self.cell(35, 6, f"${total_amount_due:,.2f}", 1, 0, 'C')
        self.cell(35, 6, f"{days_used_this_inv * 8.0:.2f}", 1, 1, 'C')
        self.ln(10)

    def add_activity_grid(self, entries, hourly_rate):
        """
        Draws the detailed list of time entries.
        hourly_rate: Must be passed as a Decimal for accurate math.
        """
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, 6, "Detailed Activity", ln=True)
        self.set_font('Helvetica', '', 9)
        
        # Column Widths
        w_date = 25
        w_desc = 85
        w_po = 30
        w_time = 20
        w_amt = 30
        
        # Headers
        self.set_fill_color(240, 240, 240)
        self.cell(w_date, 6, "Date", 1, 0, 'L', True)
        self.cell(w_desc, 6, "Description", 1, 0, 'L', True)
        self.cell(w_po, 6, "Sub-Project", 1, 0, 'L', True)
        self.cell(w_time, 6, "Time", 1, 0, 'C', True)
        self.cell(w_amt, 6, "Amount", 1, 1, 'R', True)
        
        # Rows
        total_hours = 0.0
        
        for entry in entries:
            # Calculate amount for this line
            line_hours = Decimal(str(entry['hours']))
            line_amt = line_hours * hourly_rate # Decimal * Decimal
            total_hours += float(line_hours)
            
            # Draw Cells
            self.cell(w_date, 6, str(entry['date_worked']), 1, 0, 'L')
            
            # Truncate description safely
            desc_text = (entry['description'][:45] + '..') if len(entry['description']) > 45 else entry['description']
            self.cell(w_desc, 6, desc_text, 1, 0, 'L')
            
            self.cell(w_po, 6, str(entry['PO']), 1, 0, 'L')
            self.cell(w_time, 6, f"{line_hours:.2f}", 1, 0, 'C')
            self.cell(w_amt, 6, f"${line_amt:,.2f}", 1, 1, 'R')

        # Footer Row (Total)
        self.set_font('Helvetica', 'B', 9)
        self.cell(w_date + w_desc + w_po, 6, "Total Period Hours:", 1, 0, 'R')
        self.cell(w_time, 6, f"{total_hours:.2f}", 1, 0, 'C')
        self.cell(w_amt, 6, "", 1, 1, 'R')

def generate_invoice_pdf(project_name, invoice_num, start_date, end_date,
                         loa_start, loa_end, loa_budget, daily_rate,
                         current_hours, prior_billed_days,
                         line_items):
    
    date_range_str = f"{start_date} - {end_date}"
    
    pdf = InvoicePDF(project_name=project_name, 
                     invoice_number=invoice_num, 
                     date_range=date_range_str)
    
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # 1. Math Tables
    days_this_invoice = current_hours / 8.0
    pdf.add_financial_tables(
        loa_start=loa_start,
        loa_end=loa_end,
        loa_budget_days=loa_budget,
        daily_rate=daily_rate,
        days_used_this_inv=days_this_invoice,
        prior_days_used=prior_billed_days
    )
    
    # 2. Detail Grid
    # --- MATH FIX: Calculate Hourly Rate as Decimal here too ---
    d_daily = Decimal(str(daily_rate))
    d_hourly = (d_daily / Decimal(8)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    pdf.add_activity_grid(line_items, d_hourly)
    
    return bytes(pdf.output())