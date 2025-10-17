"""
PDF generation service (scaffold)

Default engine: fpdf2 with embedded Korean TTF.
"""
from __future__ import annotations
from typing import Dict, Any, Optional
from fpdf import FPDF
import os


def generate_quotation_pdf(quotation: Dict[str, Any], items_df, *, font_path: Optional[str] = None) -> bytes:
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    # Register Korean font if provided
    if font_path and os.path.exists(font_path):
        try:
            pdf.add_font('Korean', '', font_path, uni=True)
            pdf.set_font('Korean', size=12)
        except Exception:
            pdf.set_font('Arial', size=12)
    else:
        pdf.set_font('Arial', size=12)

    # Header
    title = quotation.get('title', '견적서')
    pdf.set_xy(10, 10)
    pdf.set_font_size(16)
    pdf.cell(0, 10, title, ln=1)
    pdf.set_font_size(12)

    # Basic info
    customer = quotation.get('customer_name', '')
    site = quotation.get('site_name', '')
    pdf.cell(0, 8, f"고객사: {customer}", ln=1)
    pdf.cell(0, 8, f"현장명: {site}", ln=1)
    pdf.ln(2)

    # Items table (simplified)
    if items_df is not None and len(items_df) > 0:
        cols = [c for c in items_df.columns if c in ('item','spec','unit','qty','price','amount')]
        if not cols:
            cols = list(items_df.columns)[:6]
        # header
        pdf.set_fill_color(230,230,230)
        for c in cols:
            pdf.cell(32, 8, str(c), border=1, align='C', fill=True)
        pdf.ln()
        # rows
        for _, row in items_df.iterrows():
            for c in cols:
                pdf.cell(32, 8, str(row.get(c,''))[:30], border=1)
            pdf.ln()

    # Footer total
    total = quotation.get('total_supply_price') or quotation.get('total', 0)
    pdf.ln(3)
    pdf.cell(0, 8, f"합계(공급가): {total}", ln=1)

    return bytes(pdf.output(dest='S').encode('latin-1'))

