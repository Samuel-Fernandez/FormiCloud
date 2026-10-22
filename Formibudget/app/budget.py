from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import (
    Category,
    EntryType,
    Frequency,
    OneOffEntry,
    RecurringItem,
    RecurringOverride,
    Setting,
    WeekCorrection,
)


def week_start_of(d: date) -> date:
    """Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return (date(year + 1, 1, 1) - date(year, 12, 1)).days
    return (date(year, month + 1, 1) - date(year, month, 1)).days


@dataclass
class Occurrence:
    date: date
    name: str
    entry_type: EntryType
    amount: float
    category_id: int | None
    source: str  # "recurring" or "oneoff"
    entry_id: int  # OneOffEntry.id if source == "oneoff", RecurringItem.id if source == "recurring"


def generate_recurring_occurrences(
    item: RecurringItem, overrides: list[RecurringOverride], range_start: date, range_end: date
) -> list[Occurrence]:
    overrides_by_date = {o.occurrence_date: o for o in overrides if o.recurring_item_id == item.id}
    occurrences: list[Occurrence] = []

    if item.frequency == Frequency.weekly:
        current = item.start_date
        while current <= range_end and (item.end_date is None or current <= item.end_date):
            if current >= range_start:
                occurrences.append(_build_occurrence(item, current, overrides_by_date))
            current += timedelta(days=7)
    else:  # monthly
        n = 0
        while True:
            current = add_months(item.start_date, n)
            if current > range_end or (item.end_date is not None and current > item.end_date):
                break
            if current >= range_start:
                occurrences.append(_build_occurrence(item, current, overrides_by_date))
            n += 1

    return [o for o in occurrences if o is not None]


def _build_occurrence(item: RecurringItem, occ_date: date, overrides_by_date: dict) -> Occurrence | None:
    override = overrides_by_date.get(occ_date)
    if override and override.skipped:
        return None
    amount = override.amount if (override and override.amount is not None) else item.amount
    return Occurrence(
        date=occ_date,
        name=item.name,
        entry_type=item.entry_type,
        amount=amount,
        category_id=item.category_id,
        source="recurring",
        entry_id=item.id,
    )


def get_occurrences_in_range(session: Session, range_start: date, range_end: date) -> list[Occurrence]:
    items = session.exec(select(RecurringItem)).all()
    overrides = session.exec(select(RecurringOverride)).all()
    occurrences: list[Occurrence] = []
    for item in items:
        occurrences.extend(generate_recurring_occurrences(item, overrides, range_start, range_end))

    one_offs = session.exec(
        select(OneOffEntry).where(OneOffEntry.entry_date >= range_start, OneOffEntry.entry_date <= range_end)
    ).all()
    for entry in one_offs:
        occurrences.append(
            Occurrence(
                date=entry.entry_date,
                name=entry.name,
                entry_type=entry.entry_type,
                amount=entry.amount,
                category_id=entry.category_id,
                source="oneoff",
                entry_id=entry.id,
            )
        )

    occurrences.sort(key=lambda o: o.date)
    return occurrences


@dataclass
class CategoryTotal:
    category: Category
    spent: float
    limit: float | None

    @property
    def over_limit(self) -> bool:
        return self.limit is not None and self.spent > self.limit


@dataclass
class WeekData:
    week_start: date
    week_end: date
    days: dict[date, list[Occurrence]]
    total_income: float
    total_expense: float
    computed_balance: float
    corrected_balance: float | None
    category_totals: list[CategoryTotal]

    @property
    def final_balance(self) -> float:
        return self.corrected_balance if self.corrected_balance is not None else self.computed_balance


def get_week_data(session: Session, week_start: date) -> WeekData:
    week_end = week_start + timedelta(days=6)
    occurrences = get_occurrences_in_range(session, week_start, week_end)

    days: dict[date, list[Occurrence]] = {week_start + timedelta(days=i): [] for i in range(7)}
    for occ in occurrences:
        days[occ.date].append(occ)

    total_income = sum(o.amount for o in occurrences if o.entry_type == EntryType.income)
    total_expense = sum(o.amount for o in occurrences if o.entry_type == EntryType.expense)
    computed_balance = total_income - total_expense

    correction = session.exec(select(WeekCorrection).where(WeekCorrection.week_start == week_start)).first()

    categories = session.exec(select(Category)).all()
    category_totals = []
    for cat in categories:
        spent = sum(o.amount for o in occurrences if o.entry_type == EntryType.expense and o.category_id == cat.id)
        category_totals.append(CategoryTotal(category=cat, spent=spent, limit=cat.weekly_limit))

    return WeekData(
        week_start=week_start,
        week_end=week_end,
        days=days,
        total_income=total_income,
        total_expense=total_expense,
        computed_balance=computed_balance,
        corrected_balance=correction.corrected_balance if correction else None,
        category_totals=category_totals,
    )


@dataclass
class ProjectionPoint:
    week_start: date
    net: float
    balance: float


def get_starting_balance(session: Session) -> float:
    setting = session.get(Setting, "starting_balance")
    return float(setting.value) if setting else 0.0


def set_starting_balance(session: Session, value: float) -> None:
    setting = session.get(Setting, "starting_balance")
    if setting:
        setting.value = str(value)
    else:
        setting = Setting(key="starting_balance", value=str(value))
    session.add(setting)
    session.commit()


def get_projection(session: Session, start_week: date, weeks: int) -> list[ProjectionPoint]:
    balance = get_starting_balance(session)
    points: list[ProjectionPoint] = []
    for i in range(weeks):
        week_start = start_week + timedelta(weeks=i)
        week_data = get_week_data(session, week_start)
        net = week_data.final_balance
        balance += net
        points.append(ProjectionPoint(week_start=week_start, net=net, balance=balance))
    return points
