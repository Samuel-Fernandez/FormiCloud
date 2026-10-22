from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.budget import get_projection, get_week_data, week_start_of
from app.db import get_session
from app.models import RecurringItem, WeekCorrection

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

PROJECTION_WEEKS = 26  # ~6 months


@router.get("/")
def index():
    return RedirectResponse(url=f"/calendar/{week_start_of(date.today()).isoformat()}")


@router.get("/calendar/{week_start}")
def calendar_view(request: Request, week_start: str, session: Session = Depends(get_session)):
    ws = datetime.strptime(week_start, "%Y-%m-%d").date()
    ws = week_start_of(ws)
    week = get_week_data(session, ws)
    projection = get_projection(session, week_start_of(date.today()), PROJECTION_WEEKS)
    today = date.today()
    active_recurring = session.exec(
        select(RecurringItem).where(
            (RecurringItem.end_date.is_(None)) | (RecurringItem.end_date >= today)
        )
    ).all()

    return templates.TemplateResponse(
        "calendar.html",
        {
            "request": request,
            "week": week,
            "projection": projection,
            "active_recurring": active_recurring,
            "prev_week_iso": (ws - timedelta(days=7)).isoformat(),
            "next_week_iso": (ws + timedelta(days=7)).isoformat(),
            "today_week_iso": week_start_of(date.today()).isoformat(),
        },
    )


@router.post("/calendar/{week_start}/correction")
def set_correction(
    week_start: str,
    corrected_balance: float = Form(...),
    note: str = Form(""),
    session: Session = Depends(get_session),
):
    ws = datetime.strptime(week_start, "%Y-%m-%d").date()
    existing = session.exec(select(WeekCorrection).where(WeekCorrection.week_start == ws)).first()
    if existing:
        existing.corrected_balance = corrected_balance
        existing.note = note
    else:
        existing = WeekCorrection(week_start=ws, corrected_balance=corrected_balance, note=note)
    session.add(existing)
    session.commit()
    return RedirectResponse(url=f"/calendar/{week_start}", status_code=303)
