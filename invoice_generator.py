from fpdf import FPDF
import pandas as pd
import os

class PDF(FPDF):
    def header(self):
        # Logo: Add the image to the top left
        # Make sure 'logo.png' is in the same folder as this script
        if os.path.exists("logo.png"):
            self.image("logo.png", x=10, y=8, w=50)
        
        # Font for Company Name
        self.set_font('Arial', 'B', 15)
        # Move to the right to align with logo
        self.cell(55)
        self.cell(0, 10, 'Canto Chao, Inc.', ln=True, align='L')
        
        # Font for Header Details
        self.set_font('Arial', '', 10)
        self.cell(55)
        self.cell(0, 5, 'Consultant Services', ln=True, align='L')
        
        # Line break to separate header from content
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
    # Header row
    pdf.cell(50, 8, "LOA Dates", border=1)
    pdf.cell(40, 8, "Total LOA Budget", border=1, align='C')
    pdf.cell(40, 8, "Daily Rate", border=1, align='R')
    pdf.cell(40, 8, "Hourly Rate", border=1, align='R')
    pdf.ln()
    # Data row
    pdf.cell(50, 8, f"{loa_start} to {loa_end}", border=1)
    pdf.cell(40, 8, f"{loa_budget:.2f} Days", border=1, align='C')
    pdf.cell(40, 8, f"${daily_rate:,.2f}", border=1, align='R')
    pdf.cell(40, 8, f"${hourly_rate:,.2f}", border=1, align='R')
    pdf.ln(12)

    # --- TABLE 2: BUDGET SUMMARY ---
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, "Budget Summary for this Period", ln=True, fill=True)
    
    pdf.set_font('Arial', '', 9)
    # Headers
    pdf.cell(45, 8, "Days Used (This Invoice)", border=1, align='C')
    pdf.cell(45, 8, "Total Days Remaining", border=1, align='C')
    pdf.cell(45, 8, "Total Hours (This Invoice)", border=1, align='C')
    pdf.cell(45, 8, "Total Amount Due", border=1, align='R')
    pdf.ln()
    # Data
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
    
    # Rows
    pdf.set_font('Arial', '', 8)
    for item in line_items:
        hours = float(item['hours'])
        amount = hours * hourly_rate
        po_name = item['PO'] if item['PO'] else "General"
        
        pdf.cell(25, 7, item['date_worked'], border=1)
        
        # Handle long descriptions
        x = pdf.get_x()
        y = pdf.get_y()
        pdf.multi_cell(75, 7, item['description'], border=1, align='L')
        pdf.set_xy(x + 75, y) # Reset position to right of description
        
        pdf.cell(30, 7, po_name, border=1)
        pdf.cell(25, 7, f"{hours:.2f}", border=1, align='R')
        pdf.cell(30, 7, f"${amount:,.2f}", border=1, align='R')
        pdf.ln()
        
    # Footer Total
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(130, 8, "TOTALS FOR THIS PERIOD:", border=0, align='R')
    pdf.cell(25, 8, f"{current_hours:.2f} Hours", border=1, align='R')
    pdf.cell(30, 8, f"${invoice_total_amount:,.2f}", border=1, align='R')

    return pdf.output(dest='S').encode('latin-1')