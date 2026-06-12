import sqlite3
import os
import sys
from datetime import date
from pathlib import Path


def _get_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    data_dir = base / "bi-budget"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


DB_PATH = str(_get_data_dir() / "bi_budget.db")


def get_connection():
    return sqlite3.connect(DB_PATH)


# ============================================================
# SCHEMA MIGRATION (for existing databases)
# ============================================================

def _add_column_if_missing(cur, table, column, definition):
    cur.execute(f"PRAGMA table_info({table})")
    existing = [row[1] for row in cur.fetchall()]
    if column not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _migrate_db(conn):
    cur = conn.cursor()
    # expenses: new columns added in v2
    _add_column_if_missing(cur, "expenses", "category",      "TEXT NOT NULL DEFAULT 'General'")
    _add_column_if_missing(cur, "expenses", "due_month",     "INTEGER NOT NULL DEFAULT 1")
    _add_column_if_missing(cur, "expenses", "due_date_full", "TEXT NOT NULL DEFAULT ''")
    # One-time: the global pay_schedule.planned_savings is deprecated — savings is now per
    # income source. Zero any legacy value so the forecast doesn't double-count it against
    # the per-source savings. Idempotent: a no-op once it's already 0.
    cur.execute("UPDATE pay_schedule SET planned_savings = 0 WHERE planned_savings != 0")
    conn.commit()


# ============================================================
# INIT
# ============================================================

def init_db():
    first_time = not os.path.exists(DB_PATH)
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            amount        REAL    NOT NULL,
            due_day       INTEGER NOT NULL,
            due_month     INTEGER NOT NULL DEFAULT 1,
            due_date_full TEXT    NOT NULL DEFAULT '',
            frequency     TEXT    NOT NULL,
            category      TEXT    NOT NULL DEFAULT 'General'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS income_sources (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            amount          REAL    NOT NULL,
            frequency       TEXT    NOT NULL,
            start_date      TEXT    NOT NULL,
            planned_savings REAL    NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pay_schedule (
            id              INTEGER PRIMARY KEY CHECK(id = 1),
            last_pay        TEXT    NOT NULL,
            next_pay        TEXT    NOT NULL,
            spend_amount    REAL    NOT NULL,
            planned_savings REAL    NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS savings_balance (
            id      INTEGER PRIMARY KEY CHECK(id = 1),
            balance REAL    NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS savings_flags (
            id              INTEGER PRIMARY KEY CHECK(id = 1),
            has_set_balance INTEGER NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS savings_events (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL    NOT NULL,
            date   TEXT    NOT NULL,
            note   TEXT,
            source TEXT    NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id    INTEGER PRIMARY KEY CHECK(id = 1),
            theme TEXT    NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS expense_payments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id INTEGER NOT NULL,
            due_date   TEXT    NOT NULL,
            paid       INTEGER NOT NULL DEFAULT 0,
            UNIQUE(expense_id, due_date)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            target_amount REAL    NOT NULL,
            deadline      TEXT    NOT NULL,
            saved_amount  REAL    NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS spending_log (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            amount   REAL    NOT NULL,
            date     TEXT    NOT NULL,
            note     TEXT    NOT NULL DEFAULT '',
            category TEXT    NOT NULL DEFAULT 'General'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS account_balance (
            id      INTEGER PRIMARY KEY CHECK(id = 1),
            balance REAL    NOT NULL
        )
    """)

    conn.commit()
    _migrate_db(conn)
    conn.close()

    if first_time:
        save_setting_theme("system")
        save_savings_flag(False)
        save_savings_balance(0.0)
        save_pay_schedule("2000-01-01", "2000-01-01", 0.0, 0.0)
        save_account_balance(0.0)


# ============================================================
# EXPENSES
# ============================================================

EXPENSE_CATEGORIES = [
    "General", "Housing", "Utilities", "Insurance",
    "Transportation", "Subscriptions", "Health", "Debt",
    "Food", "Entertainment", "Other",
]

EXPENSE_FREQUENCIES = ["monthly", "quarterly", "annual", "one-time"]

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def get_expenses():
    """Returns (id, name, amount, due_day, due_month, due_date_full, frequency, category)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, amount, due_day, due_month, due_date_full, frequency, category
        FROM expenses
        ORDER BY name
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_total_monthly_expenses():
    """Annualises all expense types and returns a monthly equivalent total."""
    rows = get_expenses()
    total = 0.0
    for _id, name, amount, due_day, due_month, due_date_full, frequency, category in rows:
        if frequency == "monthly":
            total += amount
        elif frequency == "annual":
            total += amount / 12.0
        elif frequency == "quarterly":
            total += amount / 3.0
        # one-time: excluded from monthly average
    return total


def save_expense(name, amount, due_day, due_month, due_date_full,
                 frequency, category, expense_id=None):
    conn = get_connection()
    cur = conn.cursor()
    if expense_id is None:
        cur.execute("""
            INSERT INTO expenses
                (name, amount, due_day, due_month, due_date_full, frequency, category)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, amount, due_day, due_month, due_date_full, frequency, category))
    else:
        cur.execute("""
            UPDATE expenses
            SET name=?, amount=?, due_day=?, due_month=?,
                due_date_full=?, frequency=?, category=?
            WHERE id=?
        """, (name, amount, due_day, due_month, due_date_full,
              frequency, category, expense_id))
    conn.commit()
    conn.close()


def delete_expense(expense_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()


# ============================================================
# EXPENSE PAYMENTS
# ============================================================

def get_expense_payment(expense_id, due_date):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT paid FROM expense_payments
        WHERE expense_id = ? AND due_date = ?
    """, (expense_id, due_date))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def set_expense_payment(expense_id, due_date, paid):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO expense_payments (expense_id, due_date, paid)
        VALUES (?, ?, ?)
        ON CONFLICT(expense_id, due_date)
        DO UPDATE SET paid = excluded.paid
    """, (expense_id, due_date, 1 if paid else 0))
    conn.commit()
    conn.close()


# ============================================================
# INCOME SOURCES
# ============================================================

def get_income_sources():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, amount, frequency, start_date, planned_savings
        FROM income_sources ORDER BY id
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def save_income_sources(incomes):
    """incomes: list of (amount, frequency, start_date, planned_savings)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM income_sources")
    for amount, frequency, start_date, planned_savings in incomes:
        cur.execute("""
            INSERT INTO income_sources (amount, frequency, start_date, planned_savings)
            VALUES (?, ?, ?, ?)
        """, (amount, frequency, start_date, planned_savings))
    conn.commit()
    conn.close()


# ============================================================
# PAY SCHEDULE
# ============================================================

def load_pay_schedule():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT last_pay, next_pay, spend_amount, planned_savings
        FROM pay_schedule WHERE id = 1
    """)
    row = cur.fetchone()
    conn.close()
    return row


def save_pay_schedule(last_pay, next_pay, spend_amount, planned_savings):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO pay_schedule (id, last_pay, next_pay, spend_amount, planned_savings)
        VALUES (1, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            last_pay        = excluded.last_pay,
            next_pay        = excluded.next_pay,
            spend_amount    = excluded.spend_amount,
            planned_savings = excluded.planned_savings
    """, (last_pay, next_pay, spend_amount, planned_savings))
    conn.commit()
    conn.close()


# ============================================================
# SAVINGS BALANCE
# ============================================================

def load_savings_balance():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM savings_balance WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0.0


def save_savings_balance(amount):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO savings_balance (id, balance) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET balance = excluded.balance
    """, (amount,))
    conn.commit()
    conn.close()


# ============================================================
# SAVINGS FLAGS
# ============================================================

def load_savings_flag():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT has_set_balance FROM savings_flags WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    return bool(row[0]) if row else False


def save_savings_flag(value: bool):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO savings_flags (id, has_set_balance) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET has_set_balance = excluded.has_set_balance
    """, (1 if value else 0,))
    conn.commit()
    conn.close()


# ============================================================
# SAVINGS EVENTS
# ============================================================

def add_savings_event(amount: float, note: str, source: str):
    today = date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO savings_events (amount, date, note, source) VALUES (?, ?, ?, ?)
    """, (amount, today, note, source))
    cur.execute("SELECT balance FROM savings_balance WHERE id = 1")
    row = cur.fetchone()
    new_balance = (row[0] if row else 0.0) + amount
    cur.execute("UPDATE savings_balance SET balance = ? WHERE id = 1", (new_balance,))
    conn.commit()
    conn.close()


def insert_initial_savings_event(amount: float):
    today = date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO savings_events (amount, date, note, source)
        VALUES (?, ?, 'Initial Savings', 'initial')
    """, (amount, today))
    conn.commit()
    conn.close()


def get_savings_events():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT amount, date, note, source FROM savings_events
        ORDER BY date DESC, id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


# ============================================================
# SETTINGS
# ============================================================

def load_setting_theme():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT theme FROM settings WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "system"


def save_setting_theme(theme):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO settings (id, theme) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET theme = excluded.theme
    """, (theme,))
    conn.commit()
    conn.close()


# ============================================================
# GOALS
# ============================================================

def get_goals():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, target_amount, deadline, saved_amount
        FROM goals ORDER BY deadline
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def save_goal(name, target_amount, deadline, goal_id=None):
    conn = get_connection()
    cur = conn.cursor()
    if goal_id is None:
        cur.execute("""
            INSERT INTO goals (name, target_amount, deadline, saved_amount)
            VALUES (?, ?, ?, 0)
        """, (name, target_amount, deadline))
    else:
        cur.execute("""
            UPDATE goals SET name=?, target_amount=?, deadline=? WHERE id=?
        """, (name, target_amount, deadline, goal_id))
    conn.commit()
    conn.close()


def delete_goal(goal_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
    conn.commit()
    conn.close()


def add_to_goal(goal_id, amount):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE goals SET saved_amount = saved_amount + ? WHERE id = ?
    """, (amount, goal_id))
    conn.commit()
    conn.close()


# ============================================================
# SPENDING LOG
# ============================================================

SPENDING_CATEGORIES = [
    "General", "Groceries", "Gas", "Dining Out", "Entertainment",
    "Clothing", "Health", "Transportation", "Household", "Other",
]


def get_spending_log(limit=200):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, amount, date, note, category FROM spending_log
        ORDER BY date DESC, id DESC LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def add_spending_entry(amount: float, note: str, category: str):
    today = date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO spending_log (amount, date, note, category)
        VALUES (?, ?, ?, ?)
    """, (amount, today, note, category))
    conn.commit()
    conn.close()


def delete_spending_entry(entry_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM spending_log WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def get_spending_by_category(days: int = 14):
    from datetime import timedelta
    cutoff = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT category, SUM(amount) as total FROM spending_log
        WHERE date >= ? GROUP BY category ORDER BY total DESC
    """, (cutoff,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ============================================================
# ACCOUNT BALANCE  (for running-balance projection)
# ============================================================

def load_account_balance():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM account_balance WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0.0


def save_account_balance(balance: float):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO account_balance (id, balance) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET balance = excluded.balance
    """, (balance,))
    conn.commit()
    conn.close()


# ============================================================
# RESET ALL DATA
# ============================================================

def reset_all_data():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
