import sqlite3
import os
from datetime import date

import sys
from pathlib import Path

def get_app_data_dir():
    if getattr(sys, 'frozen', False):
        # Running as packaged EXE
        return Path(sys.executable).parent
    else:
        # Running from source
        return Path(__file__).parent

DB_PATH = get_app_data_dir() / "bi_budget.db"


# ============================================================
# DEBUG LOGGER HOOK
# ============================================================

DEBUG_LOGGER = None


def db_log(msg: str):
    """Send DB logs to the debug overlay if available."""
    if DEBUG_LOGGER:
        DEBUG_LOGGER.log(f"[DB] {msg}")


# ============================================================
# CONNECTION + INIT
# ============================================================

def get_connection():
    abs_path = os.path.abspath(DB_PATH)
    exists = os.path.exists(abs_path)

    db_log(f"USING DB: {abs_path}")
    db_log(f"DB EXISTS: {exists}")
    if exists:
        db_log(f"DB SIZE: {os.path.getsize(abs_path)} bytes")
    else:
        db_log("DB SIZE: <no file>")

    return sqlite3.connect(DB_PATH)



def init_db():
    db_log("INIT_DB CALLED")

    first_time = not os.path.exists(DB_PATH)
    conn = get_connection()
    cur = conn.cursor()

    # -------------------------
    # Expenses
    # -------------------------
    db_log("CREATE TABLE IF NOT EXISTS expenses")
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
    # Expense payments
    # -------------------------
    db_log("CREATE TABLE IF NOT EXISTS expense_payments")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expense_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id INTEGER NOT NULL,
            due_date TEXT NOT NULL,
            paid INTEGER NOT NULL DEFAULT 0,
            UNIQUE(expense_id, due_date)
        )
    """)

    # -------------------------
    # Income sources (FINAL SCHEMA)
    # -------------------------
    db_log("CREATE TABLE IF NOT EXISTS income_sources")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS income_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            amount REAL NOT NULL,
            frequency TEXT NOT NULL,
            start_date TEXT NOT NULL,
            planned_savings REAL NOT NULL DEFAULT 0
        )
    """)

    # MIGRATION: ensure "name" column exists
    db_log("CHECK MIGRATION: income_sources.name")
    cur.execute("PRAGMA table_info(income_sources)")
    cols = [row[1] for row in cur.fetchall()]
    if "name" not in cols:
        db_log("MIGRATION: Adding 'name' column to income_sources")
        cur.execute("ALTER TABLE income_sources ADD COLUMN name TEXT NOT NULL DEFAULT ''")

    # -------------------------
    # Pay schedule
    # -------------------------
    db_log("CREATE TABLE IF NOT EXISTS pay_schedule")
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
    db_log("CREATE TABLE IF NOT EXISTS savings_balance")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS savings_balance (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            balance REAL NOT NULL
        )
    """)

    # -------------------------
    # Savings flags
    # -------------------------
    db_log("CREATE TABLE IF NOT EXISTS savings_flags")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS savings_flags (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            has_set_balance INTEGER NOT NULL
        )
    """)

    # -------------------------
    # Savings events
    # -------------------------
    db_log("CREATE TABLE IF NOT EXISTS savings_events")
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
    db_log("CREATE TABLE IF NOT EXISTS settings")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            theme TEXT NOT NULL
        )
    """)

    conn.commit()
    db_log("COMMIT (init_db)")
    conn.close()

    if first_time:
        db_log("FIRST RUN → inserting defaults")
        save_setting_theme("system")
        save_savings_flag(False)
        save_savings_balance(0.0)
        save_pay_schedule("2000-01-01", "2000-01-01", 0.0, 0.0)


# ============================================================
# EXPENSES
# ============================================================

def get_expenses():
    db_log("EXECUTE: SELECT id, name, amount, due_day, frequency FROM expenses")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, amount, due_day, frequency FROM expenses")
    rows = cur.fetchall()
    db_log(f"FETCHED: {len(rows)} rows from expenses")
    conn.close()
    return rows


def get_total_monthly_expenses():
    rows = get_expenses()
    total = sum(
        amount
        for _id, name, amount, due_day, frequency in rows
        if frequency == "monthly"
    )
    db_log(f"CALC total_monthly_expenses → {total}")
    return total


def save_expense(name, amount, due_day, frequency, expense_id=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        if expense_id is None:
            db_log(
                f"INSERT expense: name={name}, amount={amount}, "
                f"due_day={due_day}, frequency={frequency}"
            )
            cur.execute("""
                INSERT INTO expenses (name, amount, due_day, frequency)
                VALUES (?, ?, ?, ?)
            """, (name, amount, due_day, frequency))
        else:
            db_log(
                f"UPDATE expense id={expense_id}: "
                f"name={name}, amount={amount}, due_day={due_day}, frequency={frequency}"
            )
            cur.execute("""
                UPDATE expenses
                SET name = ?, amount = ?, due_day = ?, frequency = ?
                WHERE id = ?
            """, (name, amount, due_day, frequency, expense_id))
        db_log(f"ROWCOUNT: {cur.rowcount}")
        conn.commit()
        db_log("COMMIT (save_expense)")
    except Exception as e:
        db_log(f"ERROR in save_expense: {e}")
        raise
    finally:
        conn.close()

    try:
        from .signals import signals
        db_log("SIGNAL: data_changed.emit() (save_expense)")
        signals.data_changed.emit()
    except Exception as e:
        db_log(f"SIGNAL ERROR (save_expense): {e}")


def delete_expense(expense_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        db_log(f"DELETE expense id={expense_id}")
        cur.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        db_log(f"ROWCOUNT: {cur.rowcount}")
        conn.commit()
        db_log("COMMIT (delete_expense)")
    except Exception as e:
        db_log(f"ERROR in delete_expense: {e}")
        raise
    finally:
        conn.close()

    try:
        from .signals import signals
        db_log("SIGNAL: data_changed.emit() (delete_expense)")
        signals.data_changed.emit()
    except Exception as e:
        db_log(f"SIGNAL ERROR (delete_expense): {e}")


# ============================================================
# EXPENSE PAYMENTS
# ============================================================

def get_expense_payment(expense_id, due_date):
    db_log(f"EXECUTE: get_expense_payment(expense_id={expense_id}, due_date={due_date})")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT paid
        FROM expense_payments
        WHERE expense_id = ? AND due_date = ?
    """, (expense_id, due_date))
    row = cur.fetchone()
    conn.close()
    paid = row[0] if row else 0
    db_log(f"RESULT: paid={paid}")
    return paid


def set_expense_payment(expense_id, due_date, paid):
    conn = get_connection()
    cur = conn.cursor()
    try:
        db_log(
            f"UPSERT expense_payment: expense_id={expense_id}, "
            f"due_date={due_date}, paid={paid}"
        )
        cur.execute("""
            INSERT INTO expense_payments (expense_id, due_date, paid)
            VALUES (?, ?, ?)
            ON CONFLICT(expense_id, due_date)
            DO UPDATE SET paid = excluded.paid
        """, (expense_id, due_date, paid))
        db_log(f"ROWCOUNT: {cur.rowcount}")
        conn.commit()
        db_log("COMMIT (set_expense_payment)")
    except Exception as e:
        db_log(f"ERROR in set_expense_payment: {e}")
        raise
    finally:
        conn.close()

    try:
        from .signals import signals
        db_log("SIGNAL: data_changed.emit() (set_expense_payment)")
        signals.data_changed.emit()
    except Exception as e:
        db_log(f"SIGNAL ERROR (set_expense_payment): {e}")


# ============================================================
# INCOME SOURCES
# ============================================================

def get_income_sources():
    db_log("EXECUTE: SELECT * FROM income_sources ORDER BY id")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, amount, frequency, start_date, planned_savings
        FROM income_sources
        ORDER BY id
    """)
    rows = cur.fetchall()
    db_log(f"FETCHED: {len(rows)} rows from income_sources")
    conn.close()
    return rows


def save_income_sources(incomes):
    conn = get_connection()
    cur = conn.cursor()
    try:
        db_log(f"REPLACE income_sources with {len(incomes)} rows")
        cur.execute("DELETE FROM income_sources")
        db_log(f"ROWCOUNT (delete all): {cur.rowcount}")

        for name, amount, frequency, start_date, planned_savings in incomes:
            db_log(
                f"INSERT income_source: name={name}, amount={amount}, "
                f"frequency={frequency}, start_date={start_date}, "
                f"planned_savings={planned_savings}"
            )
            cur.execute("""
                INSERT INTO income_sources (name, amount, frequency, start_date, planned_savings)
                VALUES (?, ?, ?, ?, ?)
            """, (name, amount, frequency, start_date, planned_savings))

        conn.commit()
        db_log("COMMIT (save_income_sources)")
    except Exception as e:
        db_log(f"ERROR in save_income_sources: {e}")
        raise
    finally:
        conn.close()

    try:
        from .signals import signals
        db_log("SIGNAL: data_changed.emit() (save_income_sources)")
        signals.data_changed.emit()
    except Exception as e:
        db_log(f"SIGNAL ERROR (save_income_sources): {e}")


# ============================================================
# PAY SCHEDULE
# ============================================================

def load_pay_schedule():
    db_log("EXECUTE: load_pay_schedule")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT last_pay, next_pay, spend_amount, planned_savings
        FROM pay_schedule
        WHERE id = 1
    """)
    row = cur.fetchone()
    conn.close()
    db_log(f"RESULT: {row}")
    return row


def save_pay_schedule(last_pay, next_pay, spend_amount, planned_savings):
    conn = get_connection()
    cur = conn.cursor()
    try:
        db_log(
            "UPSERT pay_schedule: "
            f"last_pay={last_pay}, next_pay={next_pay}, "
            f"spend_amount={spend_amount}, planned_savings={planned_savings}"
        )
        cur.execute("""
            INSERT INTO pay_schedule (id, last_pay, next_pay, spend_amount, planned_savings)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_pay = excluded.last_pay,
                next_pay = excluded.next_pay,
                spend_amount = excluded.spend_amount,
                planned_savings = excluded.planned_savings
        """, (last_pay, next_pay, spend_amount, planned_savings))
        db_log(f"ROWCOUNT: {cur.rowcount}")
        conn.commit()
        db_log("COMMIT (save_pay_schedule)")
    except Exception as e:
        db_log(f"ERROR in save_pay_schedule: {e}")
        raise
    finally:
        conn.close()

    try:
        from .signals import signals
        db_log("SIGNAL: data_changed.emit() (save_pay_schedule)")
        signals.data_changed.emit()
    except Exception as e:
        db_log(f"SIGNAL ERROR (save_pay_schedule): {e}")


# ============================================================
# SAVINGS BALANCE
# ============================================================

def load_savings_balance():
    db_log("EXECUTE: load_savings_balance")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM savings_balance WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    balance = row[0] if row else 0.0
    db_log(f"RESULT: balance={balance}")
    return balance


def save_savings_balance(amount):
    conn = get_connection()
    cur = conn.cursor()
    try:
        db_log(f"UPSERT savings_balance: amount={amount}")
        cur.execute("""
            INSERT INTO savings_balance (id, balance)
            VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET balance = excluded.balance
        """, (amount,))
        db_log(f"ROWCOUNT: {cur.rowcount}")
        conn.commit()
        db_log("COMMIT (save_savings_balance)")
    except Exception as e:
        db_log(f"ERROR in save_savings_balance: {e}")
        raise
    finally:
        conn.close()

    try:
        from .signals import signals
        db_log("SIGNAL: data_changed.emit() (save_savings_balance)")
        signals.data_changed.emit()
    except Exception as e:
        db_log(f"SIGNAL ERROR (save_savings_balance): {e}")


# ============================================================
# SAVINGS FLAGS
# ============================================================

def load_savings_flag():
    db_log("EXECUTE: load_savings_flag")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT has_set_balance FROM savings_flags WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    value = bool(row[0]) if row else False
    db_log(f"RESULT: has_set_balance={value}")
    return value


def save_savings_flag(value: bool):
    conn = get_connection()
    cur = conn.cursor()
    try:
        db_log(f"UPSERT savings_flag: value={value}")
        cur.execute("""
            INSERT INTO savings_flags (id, has_set_balance)
            VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET has_set_balance = excluded.has_set_balance
        """, (1 if value else 0,))
        db_log(f"ROWCOUNT: {cur.rowcount}")
        conn.commit()
        db_log("COMMIT (save_savings_flag)")
    except Exception as e:
        db_log(f"ERROR in save_savings_flag: {e}")
        raise
    finally:
        conn.close()

    try:
        from .signals import signals
        db_log("SIGNAL: data_changed.emit() (save_savings_flag)")
        signals.data_changed.emit()
    except Exception as e:
        db_log(f"SIGNAL ERROR (save_savings_flag): {e}")


# ============================================================
# SAVINGS EVENTS
# ============================================================

def add_savings_event(amount: float, note: str, source: str):
    today = date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()
    try:
        db_log(
            f"INSERT savings_event: amount={amount}, date={today}, "
            f"note={note}, source={source}"
        )
        cur.execute("""
            INSERT INTO savings_events (amount, date, note, source)
            VALUES (?, ?, ?, ?)
        """, (amount, today, note, source))

        cur.execute("SELECT balance FROM savings_balance WHERE id = 1")
        row = cur.fetchone()
        old_balance = row[0] if row else 0.0
        new_balance = old_balance + amount
        db_log(f"BALANCE: {old_balance} → {new_balance}")

        cur.execute("""
            UPDATE savings_balance
            SET balance = ?
            WHERE id = 1
        """, (new_balance,))

        conn.commit()
        db_log("COMMIT (add_savings_event)")
    except Exception as e:
        db_log(f"ERROR in add_savings_event: {e}")
        raise
    finally:
        conn.close()

    try:
        from .signals import signals
        db_log("SIGNAL: data_changed.emit() (add_savings_event)")
        signals.data_changed.emit()
    except Exception as e:
        db_log(f"SIGNAL ERROR (add_savings_event): {e}")


def insert_initial_savings_event(amount: float):
    today = date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    cur = conn.cursor()
    try:
        db_log(
            f"INSERT initial savings_event: amount={amount}, date={today}, "
            "note='Initial Savings', source='initial'"
        )
        cur.execute("""
            INSERT INTO savings_events (amount, date, note, source)
            VALUES (?, ?, 'Initial Savings', 'initial')
        """, (amount, today))
        conn.commit()
        db_log("COMMIT (insert_initial_savings_event)")
    except Exception as e:
        db_log(f"ERROR in insert_initial_savings_event: {e}")
        raise
    finally:
        conn.close()

    try:
        from .signals import signals
        db_log("SIGNAL: data_changed.emit() (insert_initial_savings_event)")
        signals.data_changed.emit()
    except Exception as e:
        db_log(f"SIGNAL ERROR (insert_initial_savings_event): {e}")


def get_savings_events():
    db_log("EXECUTE: get_savings_events")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT amount, date, note, source
        FROM savings_events
        ORDER BY date DESC, id DESC
    """)
    rows = cur.fetchall()
    db_log(f"FETCHED: {len(rows)} rows from savings_events")
    conn.close()
    return rows


# ============================================================
# SETTINGS
# ============================================================

def load_setting_theme():
    db_log("EXECUTE: load_setting_theme")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT theme FROM settings WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    theme = row[0] if row else "system"
    db_log(f"RESULT: theme={theme}")
    return theme


def save_setting_theme(theme):
    conn = get_connection()
    cur = conn.cursor()
    try:
        db_log(f"UPSERT setting_theme: theme={theme}")
        cur.execute("""
            INSERT INTO settings (id, theme)
            VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET theme = excluded.theme
        """, (theme,))
        db_log(f"ROWCOUNT: {cur.rowcount}")
        conn.commit()
        db_log("COMMIT (save_setting_theme)")
    except Exception as e:
        db_log(f"ERROR in save_setting_theme: {e}")
        raise
    finally:
        conn.close()


# ============================================================
# RESET ALL DATA
# ============================================================

def reset_all_data():
    db_log("RESET_ALL_DATA called")
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        db_log("DB FILE DELETED")
    else:
        db_log("DB FILE NOT FOUND (nothing to delete)")

    init_db()

    try:
        from .signals import signals
        db_log("SIGNAL: data_changed.emit() (reset_all_data)")
        signals.data_changed.emit()
    except Exception as e:
        db_log(f"SIGNAL ERROR (reset_all_data): {e}")


def debug_print_income_sources():
    db_log("DEBUG PRINT income_sources")
    conn = get_connection()
    cur = conn.cursor()
    for row in cur.execute("SELECT * FROM income_sources"):
        db_log(f"ROW: {row}")
    conn.close()
