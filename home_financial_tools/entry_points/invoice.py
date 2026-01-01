import argparse
import datetime
import logging
import os
from typing import List, Optional, Tuple

from dateutil.relativedelta import relativedelta

from home_financial_tools.pdf.invoice import Address, WeekBill, generate_pdf_to_fp

DEFAULT_HOURLY_RATE = 225
BILLING_ADDRESS = {
    "company_name": "Iris Software, Inc.",
    "recipient": "Accounts Payable",
    "street": "200 Metroplex Drive, Suite 300",
    "city": "Edison",
    "state": "NJ",
    "zip_code": "08817-2600",
}


def _convert_to_date(string: str) -> datetime.date:
    return datetime.datetime.strptime(string, "%Y-%m-%d").date()


def _convert_to_days_hours(string: str) -> Tuple[int, float, Optional[float]]:
    if ":" not in string:
        raise ValueError(f": must be exists in argument: {string}")

    items = string.split(":", 2)
    if len(items) > 3:
        raise ValueError("only allow 2 colons")

    if len(items) == 2:
        days, hours = items
        rate = None
    else:
        days, hours, rate = items
        rate = float(rate)

    return int(days), float(hours), rate


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Invoice Generator", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--start-date", "-s", type=_convert_to_date, required=True, help="start date, must be YYYY-MM-DD"
    )
    parser.add_argument("--invoice-number", "-i", type=int, required=True, help="invoice number")
    parser.add_argument("--directory", "-o", required=True, help="output PDF file for invoice")
    parser.add_argument("--padding", "-p", type=int, default=6, help="padding spaces")
    parser.add_argument(
        "--default-hour-rating",
        "-d",
        type=float,
        default=DEFAULT_HOURLY_RATE,
        help="default hour rate if not specified",
    )
    parser.add_argument(
        "days_hours",
        type=_convert_to_days_hours,
        nargs="+",
        help="days and hours for each week, the format is <days>:<hours>[:rate]",
    )

    return parser.parse_args()


def generate_invoice(args: argparse.Namespace) -> None:
    start_date = args.start_date

    if not os.path.isdir(args.directory):
        raise NotADirectoryError(f"not directory: {args.directory}")

    bills: List[WeekBill] = []
    current_start = start_date
    for days, hours, hour_rate in args.days_hours:
        if hour_rate is None:
            hour_rate = args.default_hour_rating

        next_start_date = current_start + relativedelta(days=days)
        end_date = next_start_date - relativedelta(days=1)
        bills.append(WeekBill(hour_rate=hour_rate, quantity=hours, start_date=current_start, end_date=end_date))
        current_start = next_start_date

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

    output_path = os.path.join(
        args.directory,
        f"{corp_address.company_name.lower().replace(' ', '_')}_invoice_{args.invoice_number}_"
        f"{start_date.strftime('%Y%m%d')}.pdf",
    )

    with open(output_path, "wb") as f:
        generate_pdf_to_fp(corp_address, bill_address, bills, args.invoice_number, f)


def main() -> None:
    logging.basicConfig()
    generate_invoice(get_args())


if __name__ == "__main__":
    main()
