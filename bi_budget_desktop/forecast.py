import datetime
from dataclasses import dataclass
from typing import List, Optional

from .database import (
    get_income_sources,
    get_expenses,
    load_pay_schedule,
)


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class IncomeWindowForecast:
    income_id: int
    amount: float
    next_pay: datetime.date
    window_start: datetime.date
    window_end: datetime.date
    total_expenses: float
    hold_back: float


@dataclass
class CombinedForecast:
    start_date: datetime.date
    end_date: datetime.date
    total_income: float
    total_expenses: float
    average_spending: float
    planned_savings: float
    total_hold_back: float
    safe_to_spend: float


@dataclass
class ThreeCheckMonthInfo:
    year: int
    month: int
    pay_dates: List[datetime.date]


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _parse_date(date_str: str) -> datetime.date:
    return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()


def _biweekly_next_pay(start_date: datetime.date, today: datetime.date) -> datetime.date:
    d = start_date
    while d < today:
        d += datetime.timedelta(days=14)
    return d


def _load_schedule_values():
    row = load_pay_schedule()
    if not row:
        return 0.0, 0.0
    _last, _next, spend, planned_savings = row
    return float(spend), float(planned_savings)


# ============================================================
# EXPENSE EXPANSION (MONTHLY RECURRING)
# ============================================================

def _expand_monthly_expenses(today: datetime.date, months_ahead: int = 3):
    """
    Convert monthly recurring expenses into actual due dates
    for the next N months.
    """
    rows = get_expenses()
    expanded = []

    for _id, name, amount, due_day, frequency in rows:
        if frequency != "monthly":
            continue

        year = today.year
        month = today.month

        for i in range(months_ahead):
            m = month + i
            y = year + (m - 1) // 12
            m = ((m - 1) % 12) + 1

            # Clamp day to end of month (e.g., Feb 30 → Feb 28)
            last_day = (datetime.date(y, m + 1, 1) - datetime.timedelta(days=1)).day \
                if m < 12 else \
                (datetime.date(y + 1, 1, 1) - datetime.timedelta(days=1)).day

            d = min(due_day, last_day)
            due_date = datetime.date(y, m, d)

            if due_date >= today:
                expanded.append((_id, name, amount, due_date, frequency))

    return expanded


def _get_expenses_in_window(start_date: datetime.date, end_date: datetime.date):
    """
    Returns all monthly recurring expenses whose generated due dates
    fall within the paycheck window.
    """
    expenses = _expand_monthly_expenses(start_date)
    results = []

    for _id, name, amount, due_date, frequency in expenses:
        if start_date <= due_date <= end_date:
            results.append((_id, name, amount, due_date, frequency))

    return results


# ============================================================
# INCOME WINDOW FORECASTING
# ============================================================

def calculate_income_windows(today: Optional[datetime.date] = None) -> List[IncomeWindowForecast]:
    if today is None:
        today = datetime.date.today()

    incomes = get_income_sources()
    income_next = []

    # All incomes are bi-weekly
    for income_id, amount, frequency, start_str in incomes:
        start = _parse_date(start_str)
        next_pay = _biweekly_next_pay(start, today)
        income_next.append((income_id, amount, next_pay))

    # Sort by next paycheck date
    income_next.sort(key=lambda x: x[2])

    forecasts: List[IncomeWindowForecast] = []
    if not income_next:
        return forecasts

    prev_boundary = today

    for income_id, amount, next_pay in income_next:
        window_start = prev_boundary
        window_end = next_pay

        expenses = _get_expenses_in_window(window_start, window_end)
        total_expenses = sum(e[2] for e in expenses)

        # If paycheck < expenses, you must hold back from previous checks
        hold_back = max(0.0, total_expenses - amount)

        forecasts.append(
            IncomeWindowForecast(
                income_id=income_id,
                amount=amount,
                next_pay=next_pay,
                window_start=window_start,
                window_end=window_end,
                total_expenses=total_expenses,
                hold_back=hold_back,
            )
        )

        prev_boundary = next_pay

    return forecasts


# ============================================================
# COMBINED FORECAST
# ============================================================

def calculate_combined_forecast(today: Optional[datetime.date] = None) -> CombinedForecast:
    if today is None:
        today = datetime.date.today()

    income_windows = calculate_income_windows(today)
    avg_spending, planned_savings = _load_schedule_values()

    total_income = sum(w.amount for w in income_windows)
    total_expenses = sum(w.total_expenses for w in income_windows)
    total_hold_back = sum(w.hold_back for w in income_windows)

    # avg_spending and planned_savings are treated as per-period totals
    required = total_expenses + avg_spending + planned_savings
    safe_to_spend = max(0.0, total_income - required)

    if income_windows:
        end_date = max(w.window_end for w in income_windows)
    else:
        end_date = today

    return CombinedForecast(
        start_date=today,
        end_date=end_date,
        total_income=total_income,
        total_expenses=total_expenses,
        average_spending=avg_spending,
        planned_savings=planned_savings,
        total_hold_back=total_hold_back,
        safe_to_spend=safe_to_spend,
    )


# ============================================================
# 3-CHECK MONTH DETECTION
# ============================================================

def _generate_biweekly_schedule(start_date: datetime.date, end_date: datetime.date) -> List[datetime.date]:
    dates = []
    d = start_date
    while d <= end_date:
        dates.append(d)
        d += datetime.timedelta(days=14)
    return dates


def find_next_three_check_month(today: Optional[datetime.date] = None, lookahead_months: int = 12) -> Optional[ThreeCheckMonthInfo]:
    if today is None:
        today = datetime.date.today()

    incomes = get_income_sources()
    if not incomes:
        return None

    end_date = today + datetime.timedelta(days=lookahead_months * 31)

    all_dates: List[datetime.date] = []
    for _id, amount, frequency, start_str in incomes:
        start = _parse_date(start_str)
        first = _biweekly_next_pay(start, today)
        all_dates.extend(_generate_biweekly_schedule(first, end_date))

    by_month = {}
    for d in all_dates:
        key = (d.year, d.month)
        by_month.setdefault(key, []).append(d)

    for (year, month), dates in sorted(by_month.items()):
        if len(dates) >= 3:
            return ThreeCheckMonthInfo(year=year, month=month, pay_dates=sorted(dates))

    return None
