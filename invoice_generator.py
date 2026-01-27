from fpdf import FPDF
import pandas as pd
import os

class PDF(FPDF):
    def header(self):
        if os.path.exists("logo.png"):
            self.image("logo.png", x=10, y=8, w=50)
        self.set_font('Arial', 'B', 15)
        self.cell(55)
        self.cell(0, 10, 'Canto Chao, Inc.', ln=True, align='L')
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
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"INVOICE #: {invoice_num}", ln=True, align='R')
    
    hourly_rate = daily_rate / 8.0
    invoice_total_amount = current_hours * hourly_rate

    # Simplified table logic to check for boot errors
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, "Activity Log", ln=True)
    for item in line_items:
        pdf.set_font('Arial', '', 8)
        pdf.cell(0, 7, f"{item['date_worked']}: {item['description'][:50]}... - {item['hours']} hrs", ln=True)

    return pdf.output()