import dataclasses
import datetime
import io
from typing import List

from fpdf import FPDF

NET = 15


@dataclasses.dataclass
class WeekBill:
    hour_rate: float
    quantity: float
    start_date: datetime.date
    end_date: datetime.date


@dataclasses.dataclass
class Address:
    recipient: str
    company_name: str
    street: str
    city: str
    state: str
    zip_code: str
    phone_number: str = None


def generate_pdf_to_fp(
    corp_address: Address,
    bill_address: Address,
    bills: List[WeekBill],
    invoice_number: int,
    output_fp: io.BytesIO,
    invoice_date: datetime.date = None,
) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=10)

    # Title
    pdf.set_font("helvetica", "B", 24)
    pdf.cell(0, 20, "INVOICE", align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Corp Name
    pdf.set_font("helvetica", size=15)
    pdf.cell(0, 10, corp_address.company_name, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=10)

    # Invoice info
    _add_invoice_information(pdf, corp_address, invoice_number, invoice_date)
    pdf.ln(5)

    # Billing info
    _add_billing_and_shipping_information(pdf, bill_address, bill_address)
    pdf.ln(5)

    # Itemized table
    _add_itemized_description_table(pdf, bills)
    pdf.ln(5)

    pdf.set_font("helvetica", size=10)
    pdf.cell(0, 10, f"Make all checks payable to {corp_address.company_name}", new_x="LMARGIN", new_y="NEXT")

    # Align Terms and following text to the bottom
    if pdf.get_y() > (pdf.h - 50):
        pdf.ln(10)
    else:
        pdf.set_y(-45)

    pdf.cell(0, 5, "Terms", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, "Thank you for your business!", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Payment terms: Net {NET}", new_x="LMARGIN", new_y="NEXT")

    pdf.output(output_fp)


def _add_invoice_information(pdf: FPDF, corp_address: Address, invoice_number: int, invoice_date: datetime.date = None) -> None:
    pdf.cell(0, 5, corp_address.street, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"{corp_address.city}, {corp_address.state} {corp_address.zip_code}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, corp_address.phone_number, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    pdf.set_font("helvetica", "B", 10)
    # Use provided invoice_date or fall back to current date
    date_to_use = invoice_date if invoice_date else datetime.datetime.now().date()
    pdf.cell(0, 5, f"Date: {date_to_use.strftime('%Y-%m-%d')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Invoice # {invoice_number}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=10)


def _add_billing_and_shipping_information(pdf: FPDF, bill_address: Address, shipping_address: Address) -> None:
    headings = ["BILL TO", "SHIP TO"]

    # Header row
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(0, 0, 0)
    pdf.set_text_color(255, 255, 255)

    col_width = pdf.epw / 2
    box_width = col_width - 2

    pdf.cell(box_width, 8, headings[0], fill=True)
    pdf.set_x(pdf.get_x() + 4)  # Gap
    pdf.cell(box_width, 8, headings[1], fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", size=10)

    # Content rows
    rows = [
        (bill_address.company_name, shipping_address.company_name),
        (bill_address.recipient, shipping_address.recipient),
        (bill_address.street, shipping_address.street),
        (
            f"{bill_address.city}, {bill_address.state} {bill_address.zip_code}",
            f"{shipping_address.city}, {shipping_address.state} {shipping_address.zip_code}",
        ),
    ]

    for r1, r2 in rows:
        pdf.cell(col_width, 5, r1)
        pdf.cell(col_width, 5, r2, new_x="LMARGIN", new_y="NEXT")


def _add_itemized_description_table(pdf: FPDF, bills: List[WeekBill]) -> None:
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(0, 0, 0)
    pdf.set_text_color(255, 255, 255)

    cols = [("QUANTITY", 0.15), ("DESCRIPTION", 0.55), ("UNIT PRICE", 0.15), ("AMOUNT", 0.15)]

    for label, width_pct in cols:
        pdf.cell(pdf.epw * width_pct, 8, label, fill=True, align="R")
    pdf.ln()

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", size=10)

    total_amount = 0.0
    for i, bill in enumerate(bills):
        if i % 2 == 1:
            pdf.set_fill_color(245, 245, 245)
        else:
            pdf.set_fill_color(255, 255, 255)

        qty = f"{bill.quantity:.1f}"
        desc = f"{bill.start_date.strftime('%B %d %Y')} - {bill.end_date.strftime('%B %d %Y')}"
        price = f"${bill.hour_rate:,.2f}"
        amount = f"${bill.hour_rate * bill.quantity:,.2f}"

        pdf.cell(pdf.epw * 0.15, 8, qty, fill=True, align="L")
        pdf.cell(pdf.epw * 0.55, 8, desc, fill=True, align="R")
        pdf.cell(pdf.epw * 0.15, 8, price, fill=True, align="R")
        pdf.cell(pdf.epw * 0.15, 8, amount, fill=True, align="R")
        pdf.ln()

        total_amount += bill.hour_rate * bill.quantity

    # Total row
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(pdf.epw * 0.85, 8, "Total", align="R")
    pdf.cell(pdf.epw * 0.15, 8, f"${total_amount:,.2f}", align="R")
    pdf.ln()
