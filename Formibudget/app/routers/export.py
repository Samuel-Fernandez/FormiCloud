from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from app.db import get_session
from app.models import Category, OneOffEntry, RecurringItem, RecurringOverride, WeekCorrection

router = APIRouter()


@router.get("/export.json")
def export_json(session: Session = Depends(get_session)):
    data = {
        "categories": [c.model_dump(mode="json") for c in session.exec(select(Category)).all()],
        "recurring_items": [r.model_dump(mode="json") for r in session.exec(select(RecurringItem)).all()],
        "recurring_overrides": [
            o.model_dump(mode="json") for o in session.exec(select(RecurringOverride)).all()
        ],
        "oneoff_entries": [e.model_dump(mode="json") for e in session.exec(select(OneOffEntry)).all()],
        "week_corrections": [w.model_dump(mode="json") for w in session.exec(select(WeekCorrection)).all()],
    }
    return JSONResponse(content=data)
