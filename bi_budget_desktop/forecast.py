# forecast.py

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from .database import (
    get_income_sources,
    get_expenses,
    load_savings_balance,
)


# ------------------------------------------------------------
# BIWEEKLY PAYDATE HELPERS
# ------------------------------------------------------------

def _biweekly_next_pay(start_date, after_date):
    """
    Given a bi-weekly start_date, find the next paydate strictly after after_date.
    """
    d = start_date
    while d <= after_date:
        d += timedelta(days=14)
    return d


def _generate_biweekly_schedule(start_date, end_date):
    """
    Generate all bi-weekly paydates from start_date → end_date.
    """
    dates = []
    d = start_date
    while d <= end_date:
        dates.append(d)
        d += timedelta(days=14)
    return dates


# ------------------------------------------------------------
# 3-CHECK MONTH DETECTION (PER-INCOME)
# ------------------------------------------------------------

def find_three_check_month_for_income(start_date, today):
    """
    For a single income source:
    - Generate paydates far into the future
    - Find the first month with 3 paychecks
    - Return (year, month, [paydates])
    """
    # Look 18 months ahead to be safe
    horizon = today + relativedelta(months=18)

    first = _biweekly_next_pay(start_date, today - timedelta(days=60))
    paydates = _generate_biweekly_schedule(first, horizon)

    # Group paydates by (year, month)
    buckets = {}
    for d in paydates:
        key = (d.year, d.month)
        buckets.setdefault(key, []).append(d)

    # Find the earliest month with 3 paychecks
    three_months = [
        (year, month, sorted(dates))
        for (year, month), dates in buckets.items()
        if len(dates) >= 3
    ]

    if not three_months:
        return None

    # Sort by chronological order
    three_months.sort(key=lambda x: (x[0], x[1]))

    year, month, dates = three_months[0]
    return {
        "year": year,
        "month": month,
        "paydates": dates[:3],  # first 3 paydates in that month
    }


def find_earliest_three_check_cutoff(today):
    """
    Across ALL income sources:
    - Find each income's next 3-check month
    - Pick the earliest one
    - Return the date of the 3rd paycheck in that month
    """
    incomes = get_income_sources()
    results = []

    for _id, name, amount, frequency, start_str, planned_savings in incomes:
        start_date = date.fromisoformat(start_str)
        info = find_three_check_month_for_income(start_date, today)
        if info:
            # The cutoff is the 3rd paycheck date
            cutoff = info["paydates"][2]
            results.append(cutoff)

    if not results:
        # Fallback: simulate 6 months ahead
        return today + relativedelta(months=6)

    return min(results)


# ------------------------------------------------------------
# EXPENSE EXPANSION
# ------------------------------------------------------------

def _expand_monthly_expenses(expenses, start_date, end_date):
    """
    Expand monthly expenses into dated events between start_date → end_date.
    """
    events = []
    for exp_id, name, amount, due_day, frequency in expenses:
        if frequency != "monthly":
            continue

        current = start_date
        while current <= end_date:
            try:
                d = date(current.year, current.month, due_day)
            except ValueError:
                current += relativedelta(months=1)
                continue

            if start_date <= d <= end_date:
                events.append({
                    "date": d,
                    "type": "expense",
                    "name": name,
                    "amount": -abs(float(amount)),
                })

            current += relativedelta(months=1)

    return events


# ------------------------------------------------------------
# HOLD-BACK SIMULATION
# ------------------------------------------------------------

def simulate_hold_back(today):
    """
    Simulate from today → earliest 3-check cutoff.
    Start with savings balance.
    Deduct expenses.
    Add income.
    Deduct planned savings per paycheck.
    Return hold_back amount.
    """
    incomes = get_income_sources()
    expenses = get_expenses()
    savings = load_savings_balance()

    cutoff = find_earliest_three_check_cutoff(today)

    # Build all events
    events = []

    # Income events
    for _id, name, amount, frequency, start_str, planned_savings in incomes:
        start_date = date.fromisoformat(start_str)
        first = _biweekly_next_pay(start_date, today - timedelta(days=60))
        paydates = _generate_biweekly_schedule(first, cutoff)

        for d in paydates:
            if today <= d <= cutoff:
                events.append({
                    "date": d,
                    "type": "income",
                    "name": name,
                    "amount": float(amount) - float(planned_savings),
                })

    # Expense events
    events.extend(_expand_monthly_expenses(expenses, today, cutoff))

    # Sort chronologically
    events.sort(key=lambda e: (e["date"], e["name"].lower()))

    # Simulate
    running = savings
    min_balance = running

    for ev in events:
        running += ev["amount"]
        if running < min_balance:
            min_balance = running

    if min_balance < 0:
        return abs(min_balance)
    return 0.0


# ------------------------------------------------------------
# INCOME WINDOWS (PER-INCOME)
# ------------------------------------------------------------

class IncomeWindow:
    def __init__(self, name, amount, window_start, window_end, next_pay, total_expenses, per_check_expense_allocation, hold_back):
        self.name = name
        self.amount = amount
        self.window_start = window_start
        self.window_end = window_end
        self.next_pay = next_pay
        self.total_expenses = total_expenses
        self.per_check_expense_allocation = per_check_expense_allocation
        self.hold_back = hold_back


def calculate_income_windows():
    """
    Build per-income windows:
    - next paydate
    - window start/end
    - expenses in window
    - per-check allocation
    """
    today = date.today()
    incomes = get_income_sources()
    expenses = get_expenses()

    windows = []

    for _id, name, amount, frequency, start_str, planned_savings in incomes:
        start_date = date.fromisoformat(start_str)

        # Next paydate
        next_pay = _biweekly_next_pay(start_date, today)

        # Window = next_pay → next_pay + 13 days
        window_start = next_pay
        window_end = next_pay + timedelta(days=13)

        # Expand expenses in this window
        exp_events = _expand_monthly_expenses(expenses, window_start, window_end)
        total_expenses = sum(ev["amount"] for ev in exp_events)

        # Per-check allocation
        per_check = total_expenses

        windows.append(
            IncomeWindow(
                name=name,
                amount=float(amount),
                window_start=window_start,
                window_end=window_end,
                next_pay=next_pay,
                total_expenses=abs(total_expenses),
                per_check_expense_allocation=abs(per_check),
                hold_back=0,  # Dashboard computes global hold-back
            )
        )

    return windows


# ------------------------------------------------------------
# COMBINED FORECAST
# ------------------------------------------------------------

class CombinedForecast:
    def __init__(self, start_date, end_date, total_income, total_expenses, average_spending, planned_savings, total_hold_back, safe_to_spend):
        self.start_date = start_date
        self.end_date = end_date
        self.total_income = total_income
        self.total_expenses = total_expenses
        self.average_spending = average_spending
        self.planned_savings = planned_savings
        self.total_hold_back = total_hold_back
        self.safe_to_spend = safe_to_spend


def calculate_combined_forecast():
    today = date.today()
    incomes = get_income_sources()
    expenses = get_expenses()

    cutoff = find_earliest_three_check_cutoff(today)

    # Build events
    events = []

    total_planned_savings = 0.0

    # Income events
    for _id, name, amount, frequency, start_str, planned_savings in incomes:
        start_date = date.fromisoformat(start_str)
        first = _biweekly_next_pay(start_date, today - timedelta(days=60))
        paydates = _generate_biweekly_schedule(first, cutoff)

        for d in paydates:
            if today <= d <= cutoff:
                events.append({
                    "date": d,
                    "type": "income",
                    "amount": float(amount),
                })
                total_planned_savings += float(planned_savings)

    # Expense events
    exp_events = _expand_monthly_expenses(expenses, today, cutoff)
    events.extend(exp_events)

    # Sort
    events.sort(key=lambda e: (e["date"], e.get("name", "")))

    # Totals
    total_income = sum(ev["amount"] for ev in events if ev["type"] == "income")
    total_expenses = sum(abs(ev["amount"]) for ev in events if ev["type"] == "expense")

    # Average spending per paycheck
    num_checks = sum(1 for ev in events if ev["type"] == "income")
    avg_spending = total_expenses / num_checks if num_checks else 0

    # Hold-back
    hold_back = simulate_hold_back(today)

    # Safe to spend
    safe = total_income - total_expenses - total_planned_savings - hold_back

    return CombinedForecast(
        start_date=today,
        end_date=cutoff,
        total_income=total_income,
        total_expenses=total_expenses,
        average_spending=avg_spending,
        planned_savings=total_planned_savings,
        total_hold_back=hold_back,
        safe_to_spend=safe,
    )
