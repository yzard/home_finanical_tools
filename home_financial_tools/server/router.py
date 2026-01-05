import io
import logging
import re
import smtplib
from datetime import datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from home_financial_tools.pdf.invoice import Address, WeekBill, generate_pdf_to_fp
from home_financial_tools.server.auth import generate_session_token, get_current_user, verify_password

logger = logging.getLogger(__name__)


class CorporationData(BaseModel):
    company_name: str
    recipient: str
    street: str
    city: str
    state: str
    zip_code: str
    phone_number: Optional[str] = None


class AddressData(BaseModel):
    recipient: str
    company_name: str
    street: str
    city: str
    state: str
    zip_code: str


class TimeEntry(BaseModel):
    date: str
    hours: float
    hourly_rate: float
    hours_inputted: bool = False
    rate_inputted: bool = False


class GenerateRequest(BaseModel):
    invoice_number: int
    start_date: str  # YYYY-MM-DD
    end_date: Optional[str] = None  # YYYY-MM-DD
    entries: List[TimeEntry]


class SettingData(BaseModel):
    key: str
    value: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


class EmailSettingsData(BaseModel):
    gmail_account: str  # Gmail account for SMTP login
    from_email: str  # From address (can be alias)
    to_email: str
    cc_email: Optional[str] = None
    gmail_app_password: Optional[str] = None


class SendMonthlyEmailRequest(BaseModel):
    invoice_number: int
    month: int  # 1-12
    year: int


class SendEmailResponse(BaseModel):
    status: str
    message: str
    new_invoice_number: int


router = APIRouter(prefix="/api")


@router.post("/login")
async def login(request: Request, login_data: LoginRequest) -> LoginResponse:
    """
    Authenticate user and return session token.
    Rate limited to 5 attempts per minute per IP.
    """
    logger.info(f"Login attempt for username: {login_data.username}")

    # Get user credentials
    allowed_users = request.app.state.allowed_users
    logger.info(f"Available users: {list(allowed_users.keys())}")

    # Check if user exists
    if login_data.username not in allowed_users:
        logger.warning(f"User not found: {login_data.username}")
        raise HTTPException(status_code=403, detail="Invalid credentials")

    # Verify password
    password_hash = allowed_users[login_data.username]
    logger.info(f"Verifying password for user: {login_data.username}, hash type: {type(password_hash)}")

    if not verify_password(login_data.password, password_hash):
        logger.warning(f"Password verification failed for user: {login_data.username}")
        raise HTTPException(status_code=403, detail="Invalid credentials")

    logger.info(f"Password verified successfully for user: {login_data.username}")

    # Generate session token and save to database
    db = request.app.state.db
    token = generate_session_token()
    expires_at = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    db.save_session(token, login_data.username, expires_at)

    logger.info(f"Session created for user: {login_data.username}")
    return LoginResponse(token=token, username=login_data.username)


@router.post("/logout")
async def logout(request: Request, current_user: str = Depends(get_current_user)) -> dict:
    """
    Invalidate current session token.
    """
    # Get token from header and delete from database
    token = request.headers.get("X-Auth-Token")
    if token:
        db = request.app.state.db
        db.delete_session(token)

    return {"status": "success"}


@router.get("/corporation")
async def get_corp(request: Request, current_user: str = Depends(get_current_user)) -> dict:
    db = request.app.state.db
    data = db.get_corporation()
    if not data:
        return {
            "company_name": "",
            "recipient": "",
            "street": "",
            "city": "",
            "state": "",
            "zip_code": "",
            "phone_number": "",
        }
    return data


@router.post("/corporation")
async def save_corp(request: Request, data: CorporationData, current_user: str = Depends(get_current_user)) -> dict:
    db = request.app.state.db
    db.save_corporation(data.model_dump())
    return {"status": "success"}


@router.get("/bill_to")
async def get_bill_to(request: Request, current_user: str = Depends(get_current_user)) -> dict:
    db = request.app.state.db
    data = db.get_bill_to()
    if not data:
        return {"recipient": "", "company_name": "", "street": "", "city": "", "state": "", "zip_code": ""}
    return data


@router.post("/bill_to")
async def save_bill_to(request: Request, data: AddressData, current_user: str = Depends(get_current_user)) -> dict:
    db = request.app.state.db
    db.save_bill_to(data.model_dump())
    return {"status": "success"}


@router.get("/ship_to")
async def get_ship_to(request: Request, current_user: str = Depends(get_current_user)) -> dict:
    db = request.app.state.db
    data = db.get_ship_to()
    if not data:
        return {"recipient": "", "company_name": "", "street": "", "city": "", "state": "", "zip_code": ""}
    return data


@router.post("/ship_to")
async def save_ship_to(request: Request, data: AddressData, current_user: str = Depends(get_current_user)) -> dict:
    db = request.app.state.db
    db.save_ship_to(data.model_dump())
    return {"status": "success"}


@router.get("/time_entries")
async def get_entries(
    request: Request, start_date: str, end_date: str, current_user: str = Depends(get_current_user)
) -> List[dict]:
    db = request.app.state.db
    return db.get_time_entries(start_date, end_date)


@router.post("/time_entries")
async def save_entry(request: Request, entry: TimeEntry, current_user: str = Depends(get_current_user)) -> dict:
    db = request.app.state.db
    db.save_time_entry(entry.date, entry.hours, entry.hourly_rate, entry.hours_inputted, entry.rate_inputted)
    return {"status": "success"}


@router.post("/generate")
async def generate_invoice(
    request: Request, req: GenerateRequest, current_user: str = Depends(get_current_user)
) -> StreamingResponse:
    db = request.app.state.db
    corp = db.get_corporation()
    bill_to = db.get_bill_to()

    if not corp or not bill_to:
        raise HTTPException(status_code=400, detail="Corporation or Bill To info missing")

    corp_data = {k: v for k, v in corp.items() if k != "id"}
    bill_data = {k: v for k, v in bill_to.items() if k != "id"}

    corp_addr = Address(**corp_data)
    bill_addr = Address(**bill_data)

    # Sort entries by date
    sorted_entries = sorted(req.entries, key=lambda x: x.date)
    if not sorted_entries:
        raise HTTPException(status_code=400, detail="No time entries provided")

    # Range limits
    start_dt = datetime.strptime(req.start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(req.end_date, "%Y-%m-%d").date() if req.end_date else sorted_entries[-1].date

    # Group by week (Monday to Sunday), but split when hourly rate changes
    # Each row represents consecutive days with the same hourly rate
    bills: List[WeekBill] = []

    # Map daily entries for easy lookup
    entry_map: Dict[str, TimeEntry] = {e.date: e for e in sorted_entries}

    current_dt = start_dt
    while current_dt <= end_dt:
        # Find the end of the current week (Sunday) within our range limits
        # weekday() is 0 for Monday, 6 for Sunday
        days_to_sunday = 6 - current_dt.weekday()
        week_end_dt = current_dt + timedelta(days=days_to_sunday)

        if week_end_dt > end_dt:
            week_end_dt = end_dt

        # Within this week, split by rate changes
        # Track current segment: start_date, hours, rate
        segment_start_dt = None
        segment_end_dt = None
        segment_hours = 0.0
        segment_rate = None

        walk_dt = current_dt
        while walk_dt <= week_end_dt:
            date_str = walk_dt.strftime("%Y-%m-%d")

            if date_str in entry_map:
                entry = entry_map[date_str]

                if segment_rate is None:
                    # Start first segment
                    segment_rate = entry.hourly_rate
                    segment_start_dt = walk_dt
                    segment_end_dt = walk_dt
                    segment_hours = entry.hours
                elif entry.hourly_rate == segment_rate:
                    # Continue current segment (same rate)
                    segment_end_dt = walk_dt
                    segment_hours += entry.hours
                else:
                    # Rate changed - close current segment and start new one
                    bills.append(
                        WeekBill(
                            hour_rate=segment_rate,
                            quantity=segment_hours,
                            start_date=segment_start_dt,
                            end_date=segment_end_dt,
                        )
                    )

                    # Start new segment with new rate
                    segment_rate = entry.hourly_rate
                    segment_start_dt = walk_dt
                    segment_end_dt = walk_dt
                    segment_hours = entry.hours
            else:
                # No entry for this day (gap)
                # Close current segment if exists
                if segment_rate is not None:
                    bills.append(
                        WeekBill(
                            hour_rate=segment_rate,
                            quantity=segment_hours,
                            start_date=segment_start_dt,
                            end_date=segment_end_dt,
                        )
                    )
                    # Reset segment
                    segment_rate = None
                    segment_hours = 0.0
                    segment_start_dt = None
                    segment_end_dt = None

            walk_dt += timedelta(days=1)

        # Close final segment of the week if exists, or create 0-hour entry if no entries in week
        if segment_rate is not None:
            bills.append(
                WeekBill(
                    hour_rate=segment_rate, quantity=segment_hours, start_date=segment_start_dt, end_date=segment_end_dt
                )
            )
        elif current_dt <= week_end_dt:
            # Week had no entries at all - create a 0-hour entry
            # Use default rate from first entry if available, otherwise 0
            default_rate = sorted_entries[0].hourly_rate if sorted_entries else 0.0
            bills.append(WeekBill(hour_rate=default_rate, quantity=0.0, start_date=current_dt, end_date=week_end_dt))

        # Move to next week start
        current_dt = week_end_dt + timedelta(days=1)

    if not bills:
        raise HTTPException(status_code=400, detail="No billable hours found in specified range")

    buf = io.BytesIO()
    # Invoice date should be 1 day after the billing period ends
    invoice_date = end_dt + timedelta(days=1)
    generate_pdf_to_fp(corp_addr, bill_addr, bills, req.invoice_number, buf, invoice_date)
    buf.seek(0)

    # Calculate filename
    after_period_dt = end_dt + timedelta(days=1)
    date_suffix = after_period_dt.strftime("%Y%m%d")
    # Robust slugification: lowercase, replace spaces/special chars with underscore, collapse multiple underscores
    safe_corp_name = re.sub(r"[^a-z0-9]+", "_", corp["company_name"].lower()).strip("_")

    filename = f"{safe_corp_name}_invoice_{req.invoice_number}_{date_suffix}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/settings/{key}")
async def get_setting(request: Request, key: str, current_user: str = Depends(get_current_user)) -> dict:
    db = request.app.state.db
    value = db.get_setting(key)
    return {"key": key, "value": value}


@router.post("/settings")
async def save_setting(request: Request, data: SettingData, current_user: str = Depends(get_current_user)) -> dict:
    db = request.app.state.db
    db.save_setting(data.key, data.value)
    return {"status": "success"}


@router.post("/email_settings/get")
async def get_email_settings(request: Request, current_user: str = Depends(get_current_user)) -> dict:
    db = request.app.state.db
    data = db.get_email_settings()
    if not data:
        return {"gmail_account": "", "from_email": "", "to_email": "", "cc_email": "", "has_password": False}
    return {
        "gmail_account": data.get("gmail_account") or "",
        "from_email": data.get("from_email") or "",
        "to_email": data.get("to_email") or "",
        "cc_email": data.get("cc_email") or "",
        "has_password": bool(data.get("gmail_app_password")),
    }


@router.post("/email_settings/set")
async def save_email_settings(
    request: Request, data: EmailSettingsData, current_user: str = Depends(get_current_user)
) -> dict:
    db = request.app.state.db
    # If password is empty, preserve existing password
    existing = db.get_email_settings()
    save_data = data.model_dump()
    if not save_data.get("gmail_app_password") and existing:
        save_data["gmail_app_password"] = existing.get("gmail_app_password")
    db.save_email_settings(save_data)
    return {"status": "success"}


@router.post("/send_email")
async def send_monthly_email(
    request: Request, req: SendMonthlyEmailRequest, current_user: str = Depends(get_current_user)
) -> SendEmailResponse:
    logger.info(f"send_monthly_email called: invoice_number={req.invoice_number}, month={req.month}, year={req.year}")
    db = request.app.state.db

    # Get email settings
    email_settings = db.get_email_settings()
    logger.info(
        f"Email settings loaded: gmail_account={email_settings.get('gmail_account') if email_settings else None}, "
        f"from={email_settings.get('from_email') if email_settings else None}"
    )
    if not email_settings or not email_settings.get("gmail_app_password"):
        raise HTTPException(status_code=400, detail="Email settings not configured. Please set Gmail app password.")
    if not email_settings.get("gmail_account"):
        raise HTTPException(status_code=400, detail="Gmail account not configured for SMTP login.")

    # Get corporation and bill_to info
    corp = db.get_corporation()
    bill_to = db.get_bill_to()
    logger.info(f"Corp loaded: {corp.get('company_name') if corp else None}")
    logger.info(f"Bill To loaded: {bill_to.get('company_name') if bill_to else None}")
    if not corp or not bill_to:
        raise HTTPException(status_code=400, detail="Corporation or Bill To info missing")

    # Calculate date ranges for first and second half
    first_half_start = datetime(req.year, req.month, 1).date()
    first_half_end = datetime(req.year, req.month, 15).date()
    logger.info(f"Date ranges: first_half={first_half_start} to {first_half_end}")

    # Second half: 16th to end of month
    if req.month == 12:
        next_month_first = datetime(req.year + 1, 1, 1).date()
    else:
        next_month_first = datetime(req.year, req.month + 1, 1).date()
    second_half_start = datetime(req.year, req.month, 16).date()
    second_half_end = next_month_first - timedelta(days=1)

    # Get time entries for both halves
    first_half_entries = db.get_time_entries(first_half_start.strftime("%Y-%m-%d"), first_half_end.strftime("%Y-%m-%d"))
    second_half_entries = db.get_time_entries(
        second_half_start.strftime("%Y-%m-%d"), second_half_end.strftime("%Y-%m-%d")
    )

    # Filter entries with hours > 0
    first_half_entries = [e for e in first_half_entries if e.get("hours", 0) > 0]
    second_half_entries = [e for e in second_half_entries if e.get("hours", 0) > 0]
    logger.info(f"Filtered entries: first_half={len(first_half_entries)}, second_half={len(second_half_entries)}")

    # Generate PDFs for both halves (even if no hours entered)
    attachments = []
    invoice_num = req.invoice_number
    logger.info("Generating PDFs for both halves...")

    # First half PDF
    pdf_bytes, filename = _generate_invoice_pdf(
        corp, bill_to, first_half_entries, first_half_start, first_half_end, invoice_num
    )
    attachments.append((pdf_bytes, filename))
    invoice_num += 1

    # Second half PDF
    pdf_bytes, filename = _generate_invoice_pdf(
        corp, bill_to, second_half_entries, second_half_start, second_half_end, invoice_num
    )
    attachments.append((pdf_bytes, filename))
    invoice_num += 1

    logger.info(f"Generated {len(attachments)} PDF attachments")

    # Send email
    logger.info(f"Sending email to {email_settings['to_email']}...")
    _send_email_with_attachments(
        gmail_account=email_settings["gmail_account"],
        from_email=email_settings["from_email"],
        to_email=email_settings["to_email"],
        cc_email=email_settings.get("cc_email"),
        app_password=email_settings["gmail_app_password"],
        subject=f"Invoices for {datetime(req.year, req.month, 1).strftime('%B %Y')}",
        body=f"Please find attached invoices for {datetime(req.year, req.month, 1).strftime('%B %Y')}.",
        attachments=attachments,
    )
    logger.info("Email sent successfully")

    # Update invoice number in database
    db.save_setting("next_invoice_number", str(invoice_num))

    return SendEmailResponse(
        status="success", message=f"Invoices sent to {email_settings['to_email']}", new_invoice_number=invoice_num
    )


def _generate_invoice_pdf(
    corp: dict, bill_to: dict, entries: List[dict], start_date: datetime, end_date: datetime, invoice_number: int
) -> tuple:
    """Generate invoice PDF and return (pdf_bytes, filename)."""
    corp_data = {k: v for k, v in corp.items() if k != "id"}
    bill_data = {k: v for k, v in bill_to.items() if k != "id"}

    corp_addr = Address(**corp_data)
    bill_addr = Address(**bill_data)

    # Convert entries to TimeEntry-like objects and sort
    sorted_entries = sorted(entries, key=lambda x: x["date"])

    # Group by week and rate (reuse logic from generate_invoice)
    bills: List[WeekBill] = []
    entry_map = {e["date"]: e for e in sorted_entries}

    current_dt = start_date
    while current_dt <= end_date:
        days_to_sunday = 6 - current_dt.weekday()
        week_end_dt = current_dt + timedelta(days=days_to_sunday)
        if week_end_dt > end_date:
            week_end_dt = end_date

        segment_start_dt = None
        segment_end_dt = None
        segment_hours = 0.0
        segment_rate = None

        walk_dt = current_dt
        while walk_dt <= week_end_dt:
            date_str = walk_dt.strftime("%Y-%m-%d")
            if date_str in entry_map:
                entry = entry_map[date_str]
                if segment_rate is None:
                    segment_rate = entry["hourly_rate"]
                    segment_start_dt = walk_dt
                    segment_end_dt = walk_dt
                    segment_hours = entry["hours"]
                elif entry["hourly_rate"] == segment_rate:
                    segment_end_dt = walk_dt
                    segment_hours += entry["hours"]
                else:
                    bills.append(
                        WeekBill(
                            hour_rate=segment_rate,
                            quantity=segment_hours,
                            start_date=segment_start_dt,
                            end_date=segment_end_dt,
                        )
                    )
                    segment_rate = entry["hourly_rate"]
                    segment_start_dt = walk_dt
                    segment_end_dt = walk_dt
                    segment_hours = entry["hours"]
            else:
                if segment_rate is not None:
                    bills.append(
                        WeekBill(
                            hour_rate=segment_rate,
                            quantity=segment_hours,
                            start_date=segment_start_dt,
                            end_date=segment_end_dt,
                        )
                    )
                    segment_rate = None
                    segment_hours = 0.0
                    segment_start_dt = None
                    segment_end_dt = None
            walk_dt += timedelta(days=1)

        # Close final segment of the week if exists, or create 0-hour entry if no entries in week
        if segment_rate is not None:
            bills.append(
                WeekBill(
                    hour_rate=segment_rate, quantity=segment_hours, start_date=segment_start_dt, end_date=segment_end_dt
                )
            )
        elif current_dt <= week_end_dt:
            # Week had no entries at all - create a 0-hour entry
            # Use default rate from first entry if available, otherwise 0
            default_rate = sorted_entries[0]["hourly_rate"] if sorted_entries else 0.0
            bills.append(WeekBill(hour_rate=default_rate, quantity=0.0, start_date=current_dt, end_date=week_end_dt))

        current_dt = week_end_dt + timedelta(days=1)

    buf = io.BytesIO()
    invoice_date = end_date + timedelta(days=1)
    generate_pdf_to_fp(corp_addr, bill_addr, bills, invoice_number, buf, invoice_date)
    buf.seek(0)

    date_suffix = (end_date + timedelta(days=1)).strftime("%Y%m%d")
    safe_corp_name = re.sub(r"[^a-z0-9]+", "_", corp["company_name"].lower()).strip("_")
    filename = f"{safe_corp_name}_invoice_{invoice_number}_{date_suffix}.pdf"

    return buf.getvalue(), filename


def _send_email_with_attachments(
    gmail_account: str,
    from_email: str,
    to_email: str,
    cc_email: Optional[str],
    app_password: str,
    subject: str,
    body: str,
    attachments: List[tuple],
) -> None:
    """Send an email with PDF attachments via Gmail SMTP.

    Args:
        gmail_account: Gmail account for SMTP authentication
        from_email: From address shown in email (can be alias)
        to_email: Recipient email address
        cc_email: CC email addresses (comma-separated)
        app_password: Gmail app password for authentication
        subject: Email subject
        body: Email body text
        attachments: List of (pdf_bytes, filename) tuples
    """
    logger.info(
        f"Building email message: gmail_account={gmail_account}, from={from_email}, to={to_email}, cc={cc_email}"
    )

    msg = MIMEMultipart()
    msg["From"] = from_email  # Use alias as From address
    msg["To"] = to_email
    if cc_email:
        msg["Cc"] = cc_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    for pdf_bytes, filename in attachments:
        logger.info(f"Attaching PDF: {filename} ({len(pdf_bytes)} bytes)")
        pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_attachment.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(pdf_attachment)

    # Build recipient list
    recipients = [to_email]
    if cc_email:
        recipients.extend([addr.strip() for addr in cc_email.split(",") if addr.strip()])
    logger.info(f"Recipients: {recipients}")

    logger.info("Connecting to smtp.gmail.com:587...")
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        logger.info("Starting TLS...")
        server.starttls()
        logger.info(f"Logging in as {gmail_account}...")
        server.login(gmail_account, app_password)  # Login with Gmail account
        logger.info("Sending message...")
        server.send_message(msg, to_addrs=recipients)
        logger.info("Message sent successfully")
