from fpdf import FPDF
import pandas as pd
import os

class PDF(FPDF):
    def header(self):
        # Logo: Add the image to the top left
        if os.path.exists("logo.png"):
            self.image("logo.png", x=10, y=8, w=50)
        
        # Font for Company Name
        self.set_font('Arial', 'B', 15)
        self.cell(55)
        self.cell(0, 10, 'Canto Chao, Inc.', ln=True, align='L')
        
        # Font for Header Details
        self.set_font('Arial', '', 10)
        self.cell(55)
        self.cell(0, 5, 'Consultant Services', ln=True, align='L')
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

def generate_invoice_pdf(project_name, invoice_num, start_date, end_date, 
                         loa_start, loa_end, loa_budget, daily_rate, 
                         current_hours, prior_billed_days, line_items):
    
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- INVOICE DETAILS & PROJECT INFO ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"INVOICE #: {invoice_num}", ln=True, align='R')
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, f"Project: {project_name}", ln=True, align='L')
    pdf.cell(0, 5, f"Billing Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", ln=True, align='L')
    pdf.ln(5)

    # --- MATH CALCULATIONS ---
    hourly_rate = daily_rate / 8.0
    current_days = current_hours / 8.0
    total_billed_days = prior_billed_days + current_days
    remaining_days = loa_budget - total_billed_days
    invoice_total_amount = current_hours * hourly_rate

    # --- TABLE 1: LOA STATUS ---
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, "LOA Status & Rates", ln=True, fill=True)
    
    pdf.set_font('Arial', '', 9)
    pdf.cell(50, 8, "LOA Dates", border=1)
    pdf.cell(40, 8, "Total LOA Budget", border=1, align='C')
    pdf.cell(40, 8, "Daily Rate", border=1, align='R')
    pdf.cell(40, 8, "Hourly Rate", border=1, align='R')
    pdf.ln()
    pdf.cell(50, 8, f"{loa_start} to {loa_end}", border=1)
    pdf.cell(40, 8, f"{loa_budget:.2f} Days", border=1, align='C')
    pdf.cell(40, 8, f"${daily_rate:,.2f}", border=1, align='R')
    pdf.cell(40, 8, f"${hourly_rate:,.2f}", border=1, align='R')
    pdf.ln(12)

    # --- TABLE 2: BUDGET SUMMARY ---
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, "Budget Summary for this Period", ln=True, fill=True)
    
    pdf.set_font('Arial', '', 9)
    pdf.cell(45, 8, "Days Used (This Invoice)", border=1, align='C')
    pdf.cell(45, 8, "Total Days Remaining", border=1, align='C')
    pdf.cell(45, 8, "Total Hours (This Invoice)", border=1, align='C')
    pdf.cell(45, 8, "Total Amount Due", border=1, align='R')
    pdf.ln()
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(45, 10, f"{current_days:.4f} Days", border=1, align='C')
    pdf.cell(45, 10, f"{remaining_days:.4f} Days", border=1, align='C')
    pdf.cell(45, 10, f"{current_hours:.2f} Hours", border=1, align='C')
    pdf.cell(45, 10, f"${invoice_total_amount:,.2f}", border=1, align='R')
    pdf.ln(15)

    # --- TABLE 3: DETAILED ACTIVITY GRID ---
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, "Detailed Activity Log", ln=True, fill=True)
    
    # Headers
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(25, 8, "Date", border=1)
    pdf.cell(75, 8, "Description", border=1)
    pdf.cell(30, 8, "Sub-Project (PO)", border=1)
    pdf.cell(25, 8, "Hours", border=1, align='R')
    pdf.cell(30, 8, "Amount", border=1, align='R')
    pdf.ln()
    
    # Rows with Multi-cell alignment fix
    pdf.set_font('Arial', '', 8)
    for item in line_items:
        hours = float(item['hours'])
        amount = hours * hourly_rate
        po_name = item['PO'] if item['PO'] else "General"
        
        # Save current Y to calculate height
        start_y = pdf.get_y()
        
        # Date column
        pdf.cell(25, 7, item['date_worked'], border=1)
        
        # Description column (Multi-cell)
        x_before_desc = pdf.get_x()
        pdf.multi_cell(75, 7, item['description'], border=1, align='L')
        end_y = pdf.get_y()
        row_height = end_y - start_y
        
        # Return to top of row for remaining columns
        pdf.set_xy(x_before_desc + 75, start_y)
        
        pdf.cell(30, row_height, po_name, border=1)
        pdf.cell(25, row_height, f"{hours:.2f}", border=1, align='R')
        pdf.cell(30, row_height, f"${amount:,.2f}", border=1, align='R')
        
        # Move to the start of the next row
        pdf.set_y(end_y)
        
    # Footer Totals
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(130, 8, "TOTALS FOR THIS PERIOD:", border=0, align='R')
    pdf.cell(25, 8, f"{current_hours:.2f} Hours", border=1, align='R')
    pdf.cell(30, 8, f"${invoice_total_amount:,.2f}", border=1, align='R')
    
    # Audit line (Days)
    pdf.ln(8)
    pdf.cell(130, 8, "EQUIVALENT BILLABLE DAYS (8h/day):", border=0, align='R')
    pdf.cell(25, 8, f"{current_hours / 8.0:.4f}", border=1, align='R')
    pdf.cell(30, 8, "", border=0)

    return pdf.output()