import argparse
import dataclasses
import io
import os
import logging
from typing import Tuple, Optional, List

from datetime import datetime
from dateutil.relativedelta import relativedelta

from fpdf import FPDF
from fpdf.fonts import FontFace

DEFAULT_HOURLY_RATE = 225
BILLING_ADDRESS = {
    "company_name": "Iris Software, Inc.",
    "recipient": "Accounts Payable",
    "street": "200 Metroplex Drive, Suite 300",
    "city": "Edison",
    "state": "NJ",
    "zip_code": "08817-2600",
}
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


def _convert_to_date(string):
    return datetime.strptime(string, "%Y-%m-%d").date()


def _convert_to_days_hours(string) -> Tuple[int, float, Optional[float]]:
    if ":" not in string:
        raise ValueError(f": must be exists in argument: {string}")

    items = string.split(":", 2)
    if len(items) > 3:
        raise ValueError(f"only allow 2 colons")

    if len(items) == 2:
        days, hours = items
        rate = None
    else:
        days, hours, rate = items
        rate = float(rate)

    return int(days), float(hours), rate


def get_args():
    parser = argparse.ArgumentParser("Invoice Generator", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--start-date", "-s", type=_convert_to_date, required=True, help="start date, must be YYYY-MM-DD"
    )
    parser.add_argument("--invoice-number", "-i", type=int, required=True, help="invoice number")
    parser.add_argument("--directory", "-o", required=True, help="output PDF file for invoice")
    parser.add_argument("--padding", "-p", type=int, default=6, help="padding spaces")
    parser.add_argument(
        "--default-hour-rating", "-d", type=float, default=DEFAULT_HOURLY_RATE,
        help="default hour rate if not specified")
    parser.add_argument(
        "days_hours",
        type=_convert_to_days_hours,
        nargs="+",
        help="days and hours for each week, the format is <days>:<hours>[:rate]"
    )

    return parser.parse_args()


def main():
    logging.basicConfig()
    return generate_invoice(get_args())


def generate_invoice(args):
    start_date = args.start_date

    if not os.path.isdir(args.directory):
        raise NotADirectoryError(f"not directory: {args.directory}")

    bills = []
    for days, hours, hour_rate in args.days_hours:
        if hour_rate is None:
            hour_rate = args.default_hour_rating

        next_start_date = start_date + relativedelta(days=days)
        end_date = next_start_date - relativedelta(days=1)
        bills.append(WeekBill(hour_rate=hour_rate, quantity=hours, start_date=start_date, end_date=end_date))
        start_date = next_start_date

    corp_address = Address(
        company_name="Edward Tech Corporation",
        recipient="Zhuo Yin",
        street="1128 Northern Blvd., Suite 404",
        city="Manhasset",
        state="NY",
        zip_code="11030",
        phone_number="917-215-8740",
    )

    bill_address = Address(**BILLING_ADDRESS)

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
    _add_invoice_information(pdf, corp_address, args.invoice_number)
    pdf.ln(5)

    # Billing info
    _add_billing_and_shipping_information(pdf, bill_address, bill_address)
    pdf.ln(5)

    # Itemized table
    _add_itemized_description_table(pdf, bills)
    pdf.ln(5)

    pdf.set_font("helvetica", size=10)
    pdf.set_font("helvetica", size=10)
    pdf.cell(0, 10, f"Make all checks payable to {corp_address.company_name}", new_x="LMARGIN", new_y="NEXT")

    # Align Terms and following text to the bottom
    # Check if we have enough space to place it at the bottom without overlap
    # Footer starts at -45 and is about 15mm high, plus "Make all checks payable" line.
    # If the content already reached beyond -50, it's safer to just add a gap or a page break.
    if pdf.get_y() > (pdf.h - 50):
        pdf.ln(10)
    else:
        pdf.set_y(-45)

    pdf.cell(0, 5, "Terms", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, "Thank you for your business!", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Payment terms: Net {NET}", new_x="LMARGIN", new_y="NEXT")

    output_path = os.path.join(
        args.directory,
        f"{corp_address.company_name.lower().replace(' ', '_')}_invoice_{args.invoice_number}_"
        f"{start_date.strftime('%Y%m%d')}.pdf",
    )
    pdf.output(output_path)


def _add_invoice_information(pdf: FPDF, corp_address: Address, invoice_number: int):
    pdf.cell(0, 5, corp_address.street, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"{corp_address.city}, {corp_address.state} {corp_address.zip_code}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, corp_address.phone_number, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 5, f"Date: {datetime.now().strftime('%Y-%m-%d')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Invoice # {invoice_number}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", size=10)


def _add_billing_and_shipping_information(pdf: FPDF, bill_address: Address, shipping_address: Address):
    headings = ["BILL TO", "SHIP TO"]
    
    # Header row
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(0, 0, 0)
    pdf.set_text_color(255, 255, 255)
    
    col_width = pdf.epw / 2
    # Add gap between the two boxes
    box_width = col_width - 2
    
    pdf.cell(box_width, 8, headings[0], fill=True)
    pdf.set_x(pdf.get_x() + 4) # Gap
    pdf.cell(box_width, 8, headings[1], fill=True, new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", size=10)
    
    # Content rows
    rows = [
        (bill_address.company_name, shipping_address.company_name),
        (bill_address.recipient, shipping_address.recipient),
        (bill_address.street, shipping_address.street),
        (f"{bill_address.city}, {bill_address.state} {bill_address.zip_code}", 
         f"{shipping_address.city}, {shipping_address.state} {shipping_address.zip_code}")
    ]
    
    for r1, r2 in rows:
        pdf.cell(col_width, 5, r1)
        pdf.cell(col_width, 5, r2, new_x="LMARGIN", new_y="NEXT")


def _add_itemized_description_table(pdf: FPDF, bills: List[WeekBill]):
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(0, 0, 0)
    pdf.set_text_color(255, 255, 255)
    
    # Header columns: QUANTITY (15%), DESCRIPTION (55%), UNIT PRICE (15%), AMOUNT (15%)
    cols = [
        ("QUANTITY", 0.15),
        ("DESCRIPTION", 0.55),
        ("UNIT PRICE", 0.15),
        ("AMOUNT", 0.15)
    ]
    
    for label, width_pct in cols:
        pdf.cell(pdf.epw * width_pct, 8, label, fill=True, align="R")
    pdf.ln()
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", size=10)
    
    total_amount = 0
    for i, bill in enumerate(bills):
        if i % 2 == 1:
            pdf.set_fill_color(245, 245, 245) # Very light gray #F5F5F5
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


if __name__ == "__main__":
    main()
