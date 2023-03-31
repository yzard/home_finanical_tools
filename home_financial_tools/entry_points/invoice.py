import argparse
import dataclasses
import os
import typing

from datetime import datetime
from dateutil.relativedelta import relativedelta

from borb.pdf import Document
from borb.pdf.page.page import Page
from borb.pdf.canvas.layout.table.fixed_column_width_table import FixedColumnWidthTable as Table
from borb.pdf.canvas.layout.table.table import TableCell
from borb.pdf.canvas.layout.text.paragraph import Paragraph
from borb.pdf.canvas.layout.layout_element import Alignment
from borb.pdf.canvas.color.color import HexColor, X11Color
from borb.pdf.canvas.layout.page_layout.multi_column_layout import SingleColumnLayout
from borb.pdf.pdf import PDF

from decimal import Decimal

from home_library_common.utility.entry_point import add_common_options, run_entry_point

DEFAULT_RATE = 192.75


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


def _convert_to_days_hours(string) -> typing.Tuple[int, int, float]:
    if ":" not in string:
        raise ValueError(f": must be exists in argument: {string}")

    items = string.split(":", 2)
    if len(items) > 3:
        raise ValueError(f"only allow 2 colons")

    if len(items) == 2:
        days, hours = items
        rate = DEFAULT_RATE
    else:
        days, hours, rate = items

    return int(days), int(hours), float(rate)


def get_args():
    parser = argparse.ArgumentParser("Invoice Generator", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--start-date", "-s", type=_convert_to_date, required=True, help="start date, must be YYYY-MM-DD"
    )
    parser.add_argument("--invoice-number", "-i", type=int, required=True, help="invoice number")
    parser.add_argument("--directory", "-o", required=True, help="output PDF file for invoice")
    parser.add_argument(
        "days_hours", type=_convert_to_days_hours, nargs="+", help="days and hours for each week, separate by comma"
    )

    add_common_options(parser)
    return parser.parse_args()


def main():
    run_entry_point(generate_invoice, get_args())


def generate_invoice(args):
    start_date = args.start_date
    font_size = Decimal(10)

    if not os.path.isdir(args.directory):
        raise NotADirectoryError(f"not directory: {args.directory}")

    bills = []
    for days, hours, hour_rate in args.days_hours:
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

    bill_address = Address(
        company_name="BCforward",
        recipient="Accounts Payable",
        street="9777 N. College Ave",
        city="Indianapolis",
        state="IN",
        zip_code="46280",
    )

    pdf = Document()

    # Add page
    page = Page()
    pdf.add_page(page)

    page_layout = SingleColumnLayout(page)
    page_layout.vertical_margin = page.get_page_info().get_height() * Decimal(0.02)

    page_layout.add(Paragraph("INVOICE", font_size=Decimal(20), text_alignment=Alignment.CENTERED))

    # Empty paragraph for spacing
    page_layout.add(Paragraph(" ", font_size=font_size))

    page_layout.add(Paragraph("Edward Tech Corporation", font_size=Decimal(15)))

    # Invoice information table
    page_layout.add(
        _build_invoice_information(corp_address=corp_address, invoice_number=args.invoice_number, font_size=font_size)
    )

    # Empty paragraph for spacing
    page_layout.add(Paragraph(" ", font_size=font_size))

    # Billing and shipping information table
    page_layout.add(
        _build_billing_and_shipping_information(
            bill_address=bill_address, shipping_address=bill_address, font_size=font_size
        )
    )

    # Empty paragraph for spacing
    page_layout.add(Paragraph(" "))

    # Itemized description
    page_layout.add(_build_itemized_description_table(bills=bills, font_size=font_size))

    page_layout.add(Paragraph(f"Make all checks payable to {corp_address.company_name}"))

    page_layout.add(Paragraph(f" "))
    page_layout.add(Paragraph(f" "))
    page_layout.add(Paragraph(f" "))
    page_layout.add(Paragraph(f" "))
    page_layout.add(Paragraph(f" "))

    page_layout.add(Paragraph(f"Terms", font_size=font_size))
    page_layout.add(Paragraph(f"Thank you for your business!", font_size=font_size))
    page_layout.add(Paragraph(f"Payment terms: Net 60", font_size=font_size))

    with open(
        os.path.join(
            args.directory,
            f"{corp_address.company_name.lower().replace(' ', '_')}_invoice_{args.invoice_number}_"
            f"{start_date.strftime('%Y%m%d')}.pdf",
        ),
        "wb",
    ) as f:
        PDF.dumps(f, pdf)


def _build_invoice_information(corp_address: Address, invoice_number: int, font_size: Decimal):
    table_001 = Table(number_of_rows=6, number_of_columns=1)

    table_001.add(Paragraph(corp_address.street, font_size=font_size))
    table_001.add(Paragraph(f"{corp_address.city}, {corp_address.state} {corp_address.zip_code}", font_size=font_size))
    table_001.add(Paragraph(corp_address.phone_number, font_size=font_size))

    table_001.add(Paragraph(" ", font_size=font_size))

    table_001.add(
        Paragraph(
            f"Date: {datetime.now().strftime('%Y-%m-%d')}",
            font="Helvetica-Bold",
            font_size=font_size,
            horizontal_alignment=Alignment.LEFT,
        )
    )
    table_001.add(
        Paragraph(
            f"Invoice # {invoice_number}",
            font="Helvetica-Bold",
            font_size=font_size,
            horizontal_alignment=Alignment.LEFT,
        )
    )

    table_001.set_padding_on_all_cells(Decimal(2), Decimal(2), Decimal(2), Decimal(2))
    table_001.no_borders()
    return table_001


def _build_billing_and_shipping_information(bill_address: Address, shipping_address: Address, font_size: Decimal):
    table_001 = Table(number_of_rows=5, number_of_columns=2)
    table_001.add(
        Paragraph("BILL TO", background_color=HexColor("263238"), font_color=X11Color("White"), font_size=font_size)
    )
    table_001.add(
        Paragraph("SHIP TO", background_color=HexColor("263238"), font_color=X11Color("White"), font_size=font_size)
    )
    table_001.add(Paragraph(bill_address.company_name, font_size=font_size))
    table_001.add(Paragraph(shipping_address.company_name, font_size=font_size))
    table_001.add(Paragraph(bill_address.recipient, font_size=font_size))
    table_001.add(Paragraph(shipping_address.recipient, font_size=font_size))
    table_001.add(Paragraph(bill_address.street, font_size=font_size))
    table_001.add(Paragraph(shipping_address.street, font_size=font_size))
    table_001.add(Paragraph(f"{bill_address.city}, {bill_address.state} {bill_address.zip_code}", font_size=font_size))
    table_001.add(
        Paragraph(f"{shipping_address.city}, {shipping_address.state} {shipping_address.zip_code}", font_size=font_size)
    )
    table_001.set_padding_on_all_cells(Decimal(2), Decimal(2), Decimal(2), Decimal(2))
    table_001.no_borders()
    return table_001


def _build_itemized_description_table(bills: typing.List[WeekBill], font_size: Decimal):
    total_number_rows = len(bills) + 2
    total_number_columns = 6
    table_001 = Table(number_of_rows=total_number_rows, number_of_columns=total_number_columns)

    odd_color = HexColor("BBBBBB")
    even_color = HexColor("FFFFFF")
    column_name_color = HexColor("000000")
    table_001.add(
        TableCell(
            Paragraph("QUANTITY", font_color=X11Color("White"), font_size=font_size, text_alignment=Alignment.RIGHT),
            background_color=column_name_color,
        )
    )
    table_001.add(
        TableCell(
            Paragraph("DESCRIPTION", font_color=X11Color("White"), font_size=font_size, text_alignment=Alignment.RIGHT),
            background_color=column_name_color,
            col_span=3,
        )
    )
    table_001.add(
        TableCell(
            Paragraph("UNIT PRICE", font_color=X11Color("White"), font_size=font_size, text_alignment=Alignment.RIGHT),
            background_color=column_name_color,
        )
    )
    table_001.add(
        TableCell(
            Paragraph("AMOUNT", font_color=X11Color("White"), font_size=font_size, text_alignment=Alignment.RIGHT),
            background_color=column_name_color,
        )
    )

    total_amount = 0
    for row_number, bill in enumerate(bills):
        c = even_color if row_number % 2 == 0 else odd_color

        table_001.add(
            TableCell(
                Paragraph(f"{bill.quantity:.1f}", font_size=font_size, text_alignment=Alignment.RIGHT),
                background_color=c,
            )
        )
        table_001.add(
            TableCell(
                Paragraph(
                    bill.start_date.strftime("%B %d %Y") + " - " + bill.end_date.strftime("%B %d %Y"),
                    font_size=font_size,
                    text_alignment=Alignment.RIGHT,
                ),
                background_color=c,
                col_span=3,
            )
        )
        table_001.add(
            TableCell(
                Paragraph(f"${bill.hour_rate:,.2f}", font_size=font_size, text_alignment=Alignment.RIGHT),
                background_color=c,
            )
        )
        table_001.add(
            TableCell(
                Paragraph(
                    f"${bill.hour_rate * bill.quantity:,.2f}", font_size=font_size, text_alignment=Alignment.RIGHT
                ),
                background_color=c,
            )
        )
        total_amount += bill.hour_rate * bill.quantity

    table_001.add(
        TableCell(
            Paragraph("Total", font="Helvetica-Bold", font_size=font_size, horizontal_alignment=Alignment.RIGHT),
            col_span=5,
        )
    )
    table_001.add(
        TableCell(Paragraph(f"${total_amount:,.2f}", font_size=font_size, horizontal_alignment=Alignment.RIGHT))
    )
    table_001.set_padding_on_all_cells(Decimal(2), Decimal(2), Decimal(2), Decimal(2))
    table_001.no_borders()
    return table_001
