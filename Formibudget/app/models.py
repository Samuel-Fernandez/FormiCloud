from datetime import date
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class EntryType(str, Enum):
    income = "income"
    expense = "expense"


class Frequency(str, Enum):
    weekly = "weekly"
    monthly = "monthly"


class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    weekly_limit: Optional[float] = None


class RecurringItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    entry_type: EntryType
    amount: float
    frequency: Frequency
    start_date: date
    end_date: Optional[date] = None
    category_id: Optional[int] = Field(default=None, foreign_key="category.id")


class RecurringOverride(SQLModel, table=True):
    """Per-occurrence adjustment for a recurring item (amount change or skip)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    recurring_item_id: int = Field(foreign_key="recurringitem.id", index=True)
    occurrence_date: date = Field(index=True)
    amount: Optional[float] = None
    skipped: bool = False


class OneOffEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    entry_type: EntryType
    amount: float
    entry_date: date = Field(index=True)
    category_id: Optional[int] = Field(default=None, foreign_key="category.id")


class WeekCorrection(SQLModel, table=True):
    """Manual override of the final computed balance for a given week."""

    id: Optional[int] = Field(default=None, primary_key=True)
    week_start: date = Field(index=True, unique=True)
    corrected_balance: float
    note: Optional[str] = None


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str
