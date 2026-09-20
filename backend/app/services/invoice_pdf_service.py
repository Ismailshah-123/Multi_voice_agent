"""
services/invoice_pdf_service.py

WHAT THIS FILE DOES:
Generates a clean, simple PDF receipt for a payment, using fpdf2 (pure
Python, no external service, no cost). Called by billing_routes.py's
GET /invoices/{id}/pdf endpoint so a business owner can download a
receipt for their records/accounting.
"""

from fpdf import FPDF
from datetime import datetime


def generate_invoice_pdf(invoice, company_name: str, owner_email: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 14, "Payment Receipt", ln=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "AI Voice Agent Platform", ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Invoice #{str(invoice.id)[:8].upper()}", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Date: {invoice.created_at.strftime('%B %d, %Y')}", ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Billed To:", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, company_name, ln=True)
    pdf.cell(0, 8, owner_email, ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(140, 10, "Description", border="B")
    pdf.cell(50, 10, "Amount", border="B", ln=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(140, 10, f"{invoice.plan.capitalize()} Plan Subscription", border="B")
    pdf.cell(50, 10, f"${invoice.amount:,.2f} {invoice.currency.upper()}", border="B", ln=True)

    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(140, 10, "Total Paid")
    pdf.cell(50, 10, f"${invoice.amount:,.2f} {invoice.currency.upper()}", ln=True)

    pdf.ln(14)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 6, "This receipt was generated automatically. For billing questions, contact support.")

    return bytes(pdf.output())
