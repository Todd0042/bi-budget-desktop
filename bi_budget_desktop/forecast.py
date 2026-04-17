import datetime
from dataclasses import dataclass
from typing import List, Optional, Tuple

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
    start_date: datetime.date
    per_check_expense_allocation: float


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
# BASIC HELPERS
# ============================================================

def _parse_date(date_str: str) -> datetime.date:
    return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()


def _biweekly_next_pay(start_date: datetime.date, today: datetime.date) -> datetime.date:
    d = start_date
    while d < today:
        d += datetime.timedelta(days=14)
    return d


def _load_schedule_values() -> Tuple[float, float]:
    row = load_pay_schedule()
    if not row:
        return 0.0, 0.0
    _last, _next, spend, planned_savings = row
    return float(spend), float(planned_savings)


def get_total_monthly_expenses() -> float:
    rows = get_expenses()
    return sum(amount for _id, name, amount, due_day, frequency in rows if frequency == "monthly")


def _last_day_of_month(year: int, month: int) -> datetime.date:
    if month < 12:
        return datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    return datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)


# ============================================================
# EXPENSE EXPANSION
# ============================================================

def _expand_monthly_expenses(start_date: datetime.date, months_ahead: int = 3):
    rows = get_expenses()
    expanded = []

    for _id, name, amount, due_day, frequency in rows:
        if frequency != "monthly":
            continue

        year = start_date.year
        month = start_date.month

        for i in range(months_ahead):
            m = month + i
            y = year + (m - 1) // 12
            m = ((m - 1) % 12) + 1

            if m < 12:
                last_day = (datetime.date(y, m + 1, 1) - datetime.timedelta(days=1)).day
            else:
                last_day = (datetime.date(y + 1, 1, 1) - datetime.timedelta(days=1)).day

            d = min(due_day, last_day)
            due_date = datetime.date(y, m, d)

            if due_date >= start_date:
                expanded.append((_id, name, amount, due_date, frequency))

    return expanded


def _expand_monthly_expenses_until(start_date: datetime.date, cutoff_date: datetime.date):
    rows = get_expenses()
    expanded = []

    for _id, name, amount, due_day, frequency in rows:
        if frequency != "monthly":
            continue

        year = start_date.year
        month = start_date.month

        while True:
            y = year + (month - 1) // 12
            m = ((month - 1) % 12) + 1

            if m < 12:
                last_day = (datetime.date(y, m + 1, 1) - datetime.timedelta(days=1)).day
            else:
                last_day = (datetime.date(y + 1, 1, 1) - datetime.timedelta(days=1)).day

            d = min(due_day, last_day)
            due_date = datetime.date(y, m, d)

            if due_date > cutoff_date:
                break

            if due_date >= start_date:
                expanded.append((_id, name, amount, due_date, frequency))

            month += 1

    return expanded


def _get_expenses_in_window(start_date: datetime.date, end_date: datetime.date):
    expenses = _expand_monthly_expenses(start_date)
    results = []

    for _id, name, amount, due_date, frequency in expenses:
        if start_date <= due_date <= end_date:
            results.append((_id, name, amount, due_date, frequency))

    return results


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


def find_next_three_check_month(today: Optional[datetime.date] = None, lookahead_months: int = 12):
    if today is None:
        today = datetime.date.today()

    incomes = get_income_sources()
    if not incomes:
        return None

    end_date = today + datetime.timedelta(days=lookahead_months * 31)

    all_dates: List[datetime.date] = []
    for _id, amount, frequency, start_str, planned_savings in incomes:
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


def find_next_three_check_month_for_income(start_date: datetime.date, today: Optional[datetime.date] = None, lookahead_months: int = 12):
    if today is None:
        today = datetime.date.today()

    first = _biweekly_next_pay(start_date, today)
    end_date = today + datetime.timedelta(days=lookahead_months * 31)

    dates = _generate_biweekly_schedule(first, end_date)

    by_month = {}
    for d in dates:
        key = (d.year, d.month)
        by_month.setdefault(key, []).append(d)

    for (year, month), ds in sorted(by_month.items()):
        if len(ds) >= 3:
            return ThreeCheckMonthInfo(year=year, month=month, pay_dates=sorted(ds))

    return None


def _get_earliest_three_check_month(today: datetime.date) -> Optional[ThreeCheckMonthInfo]:
    incomes = get_income_sources()
    best: Optional[ThreeCheckMonthInfo] = None

    for _id, amount, frequency, start_str, planned_savings in incomes:
        start = _parse_date(start_str)
        info = find_next_three_check_month_for_income(start, today)
        if not info:
            continue
        if best is None or (info.year, info.month) < (best.year, best.month):
            best = info

    return best


# ============================================================
# ROLLING HOLD-BACK ENGINE
# ============================================================

def _build_full_timeline_required_hold_back(
    today: datetime.date,
    avg_spending: float,
) -> float:
    incomes = get_income_sources()
    if not incomes:
        return 0.0

    earliest_three = _get_earliest_three_check_month(today)
    if earliest_three:
        cutoff_date = _last_day_of_month(earliest_three.year, earliest_three.month)
    else:
        approx = today + datetime.timedelta(days=6 * 31)
        cutoff_date = _last_day_of_month(approx.year, approx.month)

    pay_map = {}

    for _id, amount, frequency, start_str, planned_savings in incomes:
        start = _parse_date(start_str)
        first_pay = _biweekly_next_pay(start, today)
        if first_pay > cutoff_date:
            continue
        d = first_pay
        while d <= cutoff_date:
            income_total, savings_total = pay_map.get(d, (0.0, 0.0))
            income_total += float(amount)
            savings_total += float(planned_savings)
            pay_map[d] = (income_total, savings_total)
            d += datetime.timedelta(days=14)

    if not pay_map:
        return 0.0

    pay_dates = sorted(pay_map.keys())
    expanded_expenses = _expand_monthly_expenses_until(today, cutoff_date)

    balance = 0.0
    min_balance = 0.0
    prev_boundary = today

    for pay_date in pay_dates:
        window_start = prev_boundary
        window_end = pay_date

        income_amount, savings_amount = pay_map[pay_date]

        total_expenses = 0.0
        for _id, name, exp_amount, due_date, frequency in expanded_expenses:
            if window_start <= due_date <= window_end:
                total_expenses += exp_amount

        net = income_amount - total_expenses - avg_spending - savings_amount

        balance += net
        if balance < min_balance:
            min_balance = balance

        prev_boundary = pay_date

    return abs(min_balance)


# ============================================================
# INCOME WINDOW FORECASTING (FIXED)
# ============================================================

def calculate_income_windows(today: Optional[datetime.date] = None) -> List[IncomeWindowForecast]:
    if today is None:
        today = datetime.date.today()

    incomes = get_income_sources()
    income_next = []

    monthly_total = get_total_monthly_expenses()
    num_sources = len(incomes)
    divisor = num_sources * 2
    per_check_allocation = monthly_total / divisor if divisor > 0 else 0.0

    for income_id, amount, frequency, start_str, planned_savings in incomes:
        start = _parse_date(start_str)
        next_pay = _biweekly_next_pay(start, today)
        income_next.append((income_id, amount, next_pay, start))

    income_next.sort(key=lambda x: x[2])

    forecasts: List[IncomeWindowForecast] = []
    if not income_next:
        return forecasts

    # FIXED: one forecast per income, no nested loop
    for income_id, amount, next_pay, start in income_next:
        previous_pay = next_pay - datetime.timedelta(days=14)

        window_start = previous_pay
        window_end = next_pay

        expenses = _get_expenses_in_window(window_start, window_end)
        total_expenses = sum(e[2] for e in expenses)

        forecasts.append(
            IncomeWindowForecast(
                income_id=income_id,
                amount=float(amount),
                next_pay=next_pay,
                window_start=window_start,
                window_end=window_end,
                total_expenses=total_expenses,
                hold_back=0.0,
                start_date=start,
                per_check_expense_allocation=per_check_allocation,
            )
        )

    avg_spending, _legacy_planned_savings = _load_schedule_values()

    required_hold_back = _build_full_timeline_required_hold_back(
        today,
        avg_spending,
    )

    for w in forecasts:
        w.hold_back = required_hold_back

    return forecasts


# ============================================================
# COMBINED FORECAST (OPTION A — CONSISTENT WINDOW)
# ============================================================

def calculate_combined_forecast(today: Optional[datetime.date] = None) -> CombinedForecast:
    if today is None:
        today = datetime.date.today()

    income_windows = calculate_income_windows(today)
    avg_spending, planned_savings = _load_schedule_values()

    total_income = sum(w.amount for w in income_windows)
    total_expenses = sum(w.total_expenses for w in income_windows)
    total_hold_back = sum(w.hold_back for w in income_windows)

    # OPTION A: Combined window = earliest start → latest end
    if income_windows:
        start_date = min(w.window_start for w in income_windows)
        end_date = max(w.window_end for w in income_windows)
    else:
        start_date = today
        end_date = today

    required = total_expenses + avg_spending + planned_savings
    safe_to_spend = max(0.0, total_income - required)

    return CombinedForecast(
        start_date=start_date,
        end_date=end_date,
        total_income=total_income,
        total_expenses=total_expenses,
        average_spending=avg_spending,
        planned_savings=planned_savings,
        total_hold_back=total_hold_back,
        safe_to_spend=safe_to_spend,
    )
