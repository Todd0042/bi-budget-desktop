import datetime
from dataclasses import dataclass
from typing import List, Optional, Tuple

from dateutil.relativedelta import relativedelta

from .database import (
    get_income_sources,
    get_expenses,
    get_total_monthly_expenses,
    load_pay_schedule,
    get_expense_payment,
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
    planned_savings: float


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


def _last_day_of_month(year: int, month: int) -> datetime.date:
    if month < 12:
        return datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    return datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)


# ============================================================
# UNIFIED EXPENSE EXPANSION  (handles all frequency types)
# ============================================================

def _expand_all_expenses(
    start_date: datetime.date,
    end_date: datetime.date,
    skip_paid: bool = True,
) -> List[Tuple]:
    """
    Returns (id, name, amount, due_date, frequency, category) for every
    expense occurrence that falls within [start_date, end_date].
    """
    rows = get_expenses()
    expanded = []

    for _id, name, amount, due_day, due_month, due_date_full, frequency, category in rows:

        if frequency == "monthly":
            year  = start_date.year
            month = start_date.month
            while True:
                y = year + (month - 1) // 12
                m = ((month - 1) % 12) + 1
                last = _last_day_of_month(y, m).day
                d    = min(due_day, last)
                due  = datetime.date(y, m, d)
                if due > end_date:
                    break
                if due >= start_date:
                    paid = get_expense_payment(_id, due.isoformat()) if skip_paid else 0
                    if not paid:
                        expanded.append((_id, name, amount, due, frequency, category))
                month += 1

        elif frequency == "annual" and due_date_full:
            anchor = datetime.date.fromisoformat(due_date_full)
            # walk backward from anchor to before start_date, then forward
            d = anchor
            while d > start_date:
                d = d - relativedelta(years=1)
            while d <= end_date:
                if d >= start_date:
                    paid = get_expense_payment(_id, d.isoformat()) if skip_paid else 0
                    if not paid:
                        expanded.append((_id, name, amount, d, frequency, category))
                d = d + relativedelta(years=1)

        elif frequency == "quarterly" and due_date_full:
            anchor = datetime.date.fromisoformat(due_date_full)
            d = anchor
            while d > start_date:
                d = d - relativedelta(months=3)
            while d <= end_date:
                if d >= start_date:
                    paid = get_expense_payment(_id, d.isoformat()) if skip_paid else 0
                    if not paid:
                        expanded.append((_id, name, amount, d, frequency, category))
                d = d + relativedelta(months=3)

        elif frequency == "one-time" and due_date_full:
            due = datetime.date.fromisoformat(due_date_full)
            if start_date <= due <= end_date:
                paid = get_expense_payment(_id, due.isoformat()) if skip_paid else 0
                if not paid:
                    expanded.append((_id, name, amount, due, frequency, category))

    return expanded


def _get_expenses_in_window(
    start_date: datetime.date,
    end_date: datetime.date,
) -> List[Tuple]:
    return _expand_all_expenses(start_date, end_date, skip_paid=True)


# ============================================================
# 3-CHECK MONTH DETECTION
# ============================================================

def _generate_biweekly_schedule(
    start_date: datetime.date,
    end_date: datetime.date,
) -> List[datetime.date]:
    dates = []
    d = start_date
    while d <= end_date:
        dates.append(d)
        d += datetime.timedelta(days=14)
    return dates


def find_next_three_check_month(
    today: Optional[datetime.date] = None,
    lookahead_months: int = 12,
) -> Optional[ThreeCheckMonthInfo]:
    """
    Returns the earliest month where any single income source individually
    receives 3 paychecks. Checks each source independently so that two
    incomes on the same schedule don't double-count.
    """
    if today is None:
        today = datetime.date.today()

    incomes = get_income_sources()
    if not incomes:
        return None

    end_date = today + datetime.timedelta(days=lookahead_months * 31)
    best: Optional[ThreeCheckMonthInfo] = None

    for _id, amount, frequency, start_str, planned_savings in incomes:
        start  = _parse_date(start_str)
        first  = _biweekly_next_pay(start, today)
        dates  = _generate_biweekly_schedule(first, end_date)

        by_month: dict = {}
        for d in dates:
            by_month.setdefault((d.year, d.month), []).append(d)

        for (year, month), month_dates in sorted(by_month.items()):
            if len(month_dates) >= 3:
                info = ThreeCheckMonthInfo(
                    year=year, month=month, pay_dates=sorted(month_dates)
                )
                if best is None or (info.year, info.month) < (best.year, best.month):
                    best = info
                break  # earliest for this income found; check next income source

    return best


def find_next_three_check_month_for_income(
    start_date: datetime.date,
    today: Optional[datetime.date] = None,
    lookahead_months: int = 12,
) -> Optional[ThreeCheckMonthInfo]:
    if today is None:
        today = datetime.date.today()

    first    = _biweekly_next_pay(start_date, today)
    end_date = today + datetime.timedelta(days=lookahead_months * 31)
    dates    = _generate_biweekly_schedule(first, end_date)

    by_month = {}
    for d in dates:
        by_month.setdefault((d.year, d.month), []).append(d)

    for (year, month), ds in sorted(by_month.items()):
        if len(ds) >= 3:
            return ThreeCheckMonthInfo(year=year, month=month, pay_dates=sorted(ds))

    return None


def _get_earliest_three_check_month(
    today: datetime.date,
) -> Optional[ThreeCheckMonthInfo]:
    incomes = get_income_sources()
    best: Optional[ThreeCheckMonthInfo] = None

    for _id, amount, frequency, start_str, planned_savings in incomes:
        start = _parse_date(start_str)
        info  = find_next_three_check_month_for_income(start, today)
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
        approx      = today + datetime.timedelta(days=6 * 31)
        cutoff_date = _last_day_of_month(approx.year, approx.month)

    pay_map = {}
    for _id, amount, frequency, start_str, planned_savings in incomes:
        start     = _parse_date(start_str)
        first_pay = _biweekly_next_pay(start, today)
        if first_pay > cutoff_date:
            continue
        d = first_pay
        while d <= cutoff_date:
            income_total, savings_total = pay_map.get(d, (0.0, 0.0))
            pay_map[d] = (income_total + float(amount), savings_total + float(planned_savings))
            d += datetime.timedelta(days=14)

    if not pay_map:
        return 0.0

    pay_dates        = sorted(pay_map.keys())
    expanded_expenses = _expand_all_expenses(today, cutoff_date, skip_paid=True)

    balance     = 0.0
    min_balance = 0.0
    prev_boundary = today

    for pay_date in pay_dates:
        window_start            = prev_boundary
        window_end              = pay_date
        income_amount, savings_amount = pay_map[pay_date]

        total_expenses = sum(
            exp_amount
            for _id, name, exp_amount, due_date, freq, cat in expanded_expenses
            if window_start <= due_date <= window_end
        )

        balance += income_amount - total_expenses - avg_spending - savings_amount
        if balance < min_balance:
            min_balance = balance
        prev_boundary = pay_date

    return abs(min_balance)


# ============================================================
# INCOME WINDOW FORECASTING
# ============================================================

def calculate_income_windows(
    today: Optional[datetime.date] = None,
) -> List[IncomeWindowForecast]:
    if today is None:
        today = datetime.date.today()

    incomes        = get_income_sources()
    monthly_total  = get_total_monthly_expenses()
    num_sources    = len(incomes)
    divisor        = num_sources * 2
    per_check_alloc = monthly_total / divisor if divisor > 0 else 0.0

    income_next = []
    for income_id, amount, frequency, start_str, planned_savings in incomes:
        start    = _parse_date(start_str)
        next_pay = _biweekly_next_pay(start, today)
        income_next.append((income_id, float(amount), next_pay, start, float(planned_savings)))

    income_next.sort(key=lambda x: x[2])

    forecasts: List[IncomeWindowForecast] = []
    for income_id, amount, next_pay, start, planned_savings in income_next:
        previous_pay  = next_pay - datetime.timedelta(days=14)
        window_start  = previous_pay
        window_end    = next_pay
        expenses      = _get_expenses_in_window(window_start, window_end)
        total_expenses = sum(e[2] for e in expenses)

        forecasts.append(IncomeWindowForecast(
            income_id=income_id,
            amount=amount,
            next_pay=next_pay,
            window_start=window_start,
            window_end=window_end,
            total_expenses=total_expenses,
            hold_back=0.0,
            start_date=start,
            per_check_expense_allocation=per_check_alloc,
            planned_savings=planned_savings,
        ))

    avg_spending, _ = _load_schedule_values()
    required_hold_back = _build_full_timeline_required_hold_back(today, avg_spending)

    for w in forecasts:
        w.hold_back = required_hold_back

    return forecasts


# ============================================================
# COMBINED FORECAST
# ============================================================

def calculate_combined_forecast(
    today: Optional[datetime.date] = None,
) -> CombinedForecast:
    if today is None:
        today = datetime.date.today()

    income_windows = calculate_income_windows(today)
    avg_spending, planned_savings = _load_schedule_values()

    total_income    = sum(w.amount for w in income_windows)
    total_expenses  = sum(w.total_expenses for w in income_windows)
    total_hold_back = sum(w.hold_back for w in income_windows)

    if income_windows:
        start_date = min(w.window_start for w in income_windows)
        end_date   = max(w.window_end   for w in income_windows)
    else:
        start_date = end_date = today

    required   = total_expenses + avg_spending + planned_savings
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


# ============================================================
# RUNNING BALANCE PROJECTION
# ============================================================

@dataclass
class BalanceEvent:
    date: datetime.date
    description: str
    amount: float          # positive = credit, negative = debit
    balance: float         # running balance after this event
    event_type: str        # "income" | "expense"


def calculate_running_balance(
    starting_balance: float,
    today: Optional[datetime.date] = None,
    weeks_ahead: int = 8,
) -> List[BalanceEvent]:
    """
    Projects the checking-account balance over the next `weeks_ahead` weeks.
    starting_balance should be the current checking account balance.
    """
    if today is None:
        today = datetime.date.today()

    end_date = today + datetime.timedelta(weeks=weeks_ahead)
    events: List[Tuple] = []   # (date, description, amount, event_type)

    # Income events
    for _id, amount, frequency, start_str, planned_savings in get_income_sources():
        start    = _parse_date(start_str)
        next_pay = _biweekly_next_pay(start, today)
        d = next_pay
        while d <= end_date:
            events.append((d, f"Paycheck #{_id}", float(amount), "income"))
            d += datetime.timedelta(days=14)

    # Expense events (all frequencies, unpaid only)
    for _id, name, amount, due_date, frequency, category in _expand_all_expenses(today, end_date, skip_paid=True):
        events.append((due_date, f"{name} ({category})", -float(amount), "expense"))

    events.sort(key=lambda e: (e[0], 0 if e[3] == "income" else 1))

    balance = starting_balance
    result: List[BalanceEvent] = []
    for d, desc, amt, etype in events:
        balance += amt
        result.append(BalanceEvent(
            date=d,
            description=desc,
            amount=amt,
            balance=balance,
            event_type=etype,
        ))

    return result
