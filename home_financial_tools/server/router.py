import io
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from home_financial_tools.pdf.invoice import Address, WeekBill, generate_pdf_to_fp
from home_financial_tools.server.auth import generate_session_token, get_current_user, verify_password


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


router = APIRouter(prefix="/api")


@router.post("/login")
async def login(request: Request, login_data: LoginRequest) -> LoginResponse:
    """
    Authenticate user and return session token.
    Rate limited to 5 attempts per minute per IP.
    """
    # Get user credentials
    allowed_users = request.app.state.allowed_users

    # Check if user exists
    if login_data.username not in allowed_users:
        raise HTTPException(status_code=403, detail="Invalid credentials")

    # Verify password
    password_hash = allowed_users[login_data.username]
    if not verify_password(login_data.password, password_hash):
        raise HTTPException(status_code=403, detail="Invalid credentials")

    # Generate session token and save to database
    db = request.app.state.db
    token = generate_session_token()
    expires_at = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    db.save_session(token, login_data.username, expires_at)

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
                    if segment_hours > 0:
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
                if segment_rate is not None and segment_hours > 0:
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

        # Close final segment of the week if exists
        if segment_rate is not None and segment_hours > 0:
            bills.append(
                WeekBill(
                    hour_rate=segment_rate, quantity=segment_hours, start_date=segment_start_dt, end_date=segment_end_dt
                )
            )

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
