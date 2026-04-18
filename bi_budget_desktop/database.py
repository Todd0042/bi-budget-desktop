import sqlite3
import os
from datetime import date

DB_PATH = "bi_budget.db"


def get_connection():
    import os
    abs_path = os.path.abspath(DB_PATH)
    print(">>> USING DB:", abs_path)
    print(">>> DB EXISTS:", os.path.exists(abs_path))
    if os.path.exists(abs_path):
        print(">>> DB SIZE:", os.path.getsize(abs_path))
    else:
        print(">>> DB SIZE: <no file>")
    return sqlite3.connect(DB_PATH)



def init_db():
    print(">>> INIT_DB CALLED")

    first_time = not os.path.exists(DB_PATH)
    conn = get_connection()
    cur = conn.cursor()

    # -------------------------
    # Expenses
    # -------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            due_day INTEGER NOT NULL,
            frequency TEXT NOT NULL
        )
    """)

    # -------------------------
    # Income sources (FINAL SCHEMA)
    # -------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS income_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            frequency TEXT NOT NULL,
            start_date TEXT NOT NULL,
            planned_savings REAL NOT NULL DEFAULT 0
        )
    """)

    # -------------------------
    # Pay schedule
    # -------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pay_schedule (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            last_pay TEXT NOT NULL,
            next_pay TEXT NOT NULL,
            spend_amount REAL NOT NULL,
            planned_savings REAL NOT NULL
        )
    """)

    # -------------------------
    # Savings balance
    # -------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS savings_balance (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            balance REAL NOT NULL
        )
    """)

    # -------------------------
    # Savings flags
    # -------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS savings_flags (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            has_set_balance INTEGER NOT NULL
        )
    """)

    # -------------------------
    # Savings events
    # -------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS savings_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            note TEXT,
            source TEXT NOT NULL
        )
    """)

    # -------------------------
    # Settings
    # -------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            theme TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

    # Initialize defaults on first run
    if first_time:
        save_setting_theme("system")
        save_savings_flag(False)
        save_savings_balance(0.0)
        save_pay_schedule("2000-01-01", "2000-01-01", 0.0, 0.0)


# ============================================================
# EXPENSES
# ============================================================

def get_expenses():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, amount, due_day, frequency FROM expenses")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_total_monthly_expenses():
    rows = get_expenses()
    return sum(
        amount
        for _id, name, amount, due_day, frequency in rows
        if frequency == "monthly"
    )



def save_expense(name, amount, due_day, frequency, expense_id=None):
    conn = get_connection()
    cur = conn.cursor()
    if expense_id is None:
        cur.execute("""
            INSERT INTO expenses (name, amount, due_day, frequency)
            VALUES (?, ?, ?, ?)
        """, (name, amount, due_day, frequency))
    else:
        cur.execute("""
            UPDATE expenses
            SET name = ?, amount = ?, due_day = ?, frequency = ?
            WHERE id = ?
        """, (name, amount, due_day, frequency, expense_id))
    conn.commit()
    conn.close()


def delete_expense(expense_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()

# ============================================================
# EXPENSE PAYMENTS (monthly bill instances)
# ============================================================

def get_expense_payment(expense_id, due_date):
    """
    Returns 1 if the bill is marked paid for that due_date, otherwise 0.
    If no row exists, returns 0 (unpaid).
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT paid
        FROM expense_payments
        WHERE expense_id = ? AND due_date = ?
    """, (expense_id, due_date))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def set_expense_payment(expense_id, due_date, paid):
    """
    Inserts or updates the paid status for a bill instance.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO expense_payments (expense_id, due_date, paid)
        VALUES (?, ?, ?)
        ON CONFLICT(expense_id, due_date)
        DO UPDATE SET paid = excluded.paid
    """, (expense_id, due_date, paid))
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
        FROM income_sources
        ORDER BY id
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def save_income_sources(incomes):
    conn = get_connection()
    cur = conn.cursor()

    # Clear existing rows first
    cur.execute("DELETE FROM income_sources")

    # Insert fresh set
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
        FROM pay_schedule
        WHERE id = 1
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
            last_pay = excluded.last_pay,
            next_pay = excluded.next_pay,
            spend_amount = excluded.spend_amount,
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
        INSERT INTO savings_balance (id, balance)
        VALUES (1, ?)
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
        INSERT INTO savings_flags (id, has_set_balance)
        VALUES (1, ?)
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
        INSERT INTO savings_events (amount, date, note, source)
        VALUES (?, ?, ?, ?)
    """, (amount, today, note, source))

    cur.execute("SELECT balance FROM savings_balance WHERE id = 1")
    row = cur.fetchone()
    old_balance = row[0] if row else 0.0
    new_balance = old_balance + amount

    cur.execute("""
        UPDATE savings_balance
        SET balance = ?
        WHERE id = 1
    """, (new_balance,))

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
        SELECT amount, date, note, source
        FROM savings_events
        ORDER BY date DESC, id DESC
    """)
    print(">>> USING DB:", os.path.abspath(DB_PATH))

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
        INSERT INTO settings (id, theme)
        VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET theme = excluded.theme
    """, (theme,))
    conn.commit()
    conn.close()


# ============================================================
# RESET ALL DATA
# ============================================================

def reset_all_data():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()

def debug_print_income_sources():
    conn = get_connection()
    cur = conn.cursor()
    print(">>> RAW income_sources TABLE:")
    for row in cur.execute("SELECT * FROM income_sources"):
        print("   ", row)
    conn.close()


