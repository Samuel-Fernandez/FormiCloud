from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import (
    Category,
    EntryType,
    Frequency,
    OneOffEntry,
    RecurringItem,
    RecurringOverride,
)

router = APIRouter()


def _redirect_to_week(week_start: str):
    return RedirectResponse(url=f"/calendar/{week_start}", status_code=303)


def _parse_optional_int(value: Optional[str]) -> Optional[int]:
    return int(value) if value else None


def _parse_optional_float(value: Optional[str]) -> Optional[float]:
    return float(value) if value else None


@router.post("/oneoff/{week_start}")
def create_oneoff(
    week_start: str,
    name: str = Form(...),
    entry_type: EntryType = Form(...),
    amount: float = Form(...),
    entry_date: str = Form(...),
    category_id: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    entry = OneOffEntry(
        name=name,
        entry_type=entry_type,
        amount=amount,
        entry_date=datetime.strptime(entry_date, "%Y-%m-%d").date(),
        category_id=_parse_optional_int(category_id),
    )
    session.add(entry)
    session.commit()
    return _redirect_to_week(week_start)


@router.post("/oneoff/{entry_id}/delete/{week_start}")
def delete_oneoff(entry_id: int, week_start: str, session: Session = Depends(get_session)):
    entry = session.get(OneOffEntry, entry_id)
    if entry:
        session.delete(entry)
        session.commit()
    return _redirect_to_week(week_start)


@router.post("/recurring/{week_start}")
def create_recurring(
    week_start: str,
    name: str = Form(...),
    entry_type: EntryType = Form(...),
    amount: float = Form(...),
    frequency: Frequency = Form(...),
    start_date: str = Form(...),
    end_date: Optional[str] = Form(None),
    category_id: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    item = RecurringItem(
        name=name,
        entry_type=entry_type,
        amount=amount,
        frequency=frequency,
        start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
        end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None,
        category_id=_parse_optional_int(category_id),
    )
    session.add(item)
    session.commit()
    return _redirect_to_week(week_start)


@router.post("/recurring/{item_id}/end/{week_start}")
def end_recurring(item_id: int, week_start: str, session: Session = Depends(get_session)):
    """Stop a recurring item as of today, keeping past occurrences in history."""
    item = session.get(RecurringItem, item_id)
    if item:
        item.end_date = date.today() - timedelta(days=1)
        session.add(item)
        session.commit()
    return _redirect_to_week(week_start)


@router.post("/recurring/{item_id}/skip/{occurrence_date}/{week_start}")
def skip_recurring_occurrence(
    item_id: int, occurrence_date: str, week_start: str, session: Session = Depends(get_session)
):
    """Remove a single occurrence of a recurring item, keeping the recurrence itself intact."""
    occ_date = datetime.strptime(occurrence_date, "%Y-%m-%d").date()
    override = session.exec(
        select(RecurringOverride).where(
            RecurringOverride.recurring_item_id == item_id,
            RecurringOverride.occurrence_date == occ_date,
        )
    ).first()
    if override:
        override.skipped = True
    else:
        override = RecurringOverride(recurring_item_id=item_id, occurrence_date=occ_date, skipped=True)
    session.add(override)
    session.commit()
    return _redirect_to_week(week_start)


@router.post("/recurring/{item_id}/delete-all/{week_start}")
def delete_recurring_completely(item_id: int, week_start: str, session: Session = Depends(get_session)):
    """Delete a recurring item entirely, including its past occurrences (use for mistakes)."""
    item = session.get(RecurringItem, item_id)
    if item:
        overrides = session.exec(
            select(RecurringOverride).where(RecurringOverride.recurring_item_id == item_id)
        ).all()
        for override in overrides:
            session.delete(override)
        session.delete(item)
        session.commit()
    return _redirect_to_week(week_start)


@router.get("/recurring")
def list_recurring(session: Session = Depends(get_session)):
    items = session.exec(select(RecurringItem)).all()
    return items


@router.post("/categories")
def create_category(
    week_start: str = Form(...),
    name: str = Form(...),
    weekly_limit: Optional[str] = Form(None),
    session: Session = Depends(get_session),
):
    category = Category(name=name, weekly_limit=_parse_optional_float(weekly_limit))
    session.add(category)
    session.commit()
    return _redirect_to_week(week_start)


@router.post("/categories/{category_id}/delete/{week_start}")
def delete_category(category_id: int, week_start: str, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if category:
        session.delete(category)
        session.commit()
    return _redirect_to_week(week_start)
