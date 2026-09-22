import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "allergo.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS symptom_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            logged_at TEXT NOT NULL,
            body_zone TEXT NOT NULL,
            symptom TEXT NOT NULL,
            severity INTEGER NOT NULL,
            allergen TEXT,
            note TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def add_entry(body_zone: str, symptom: str, severity: int, allergen: str, note: str = "", logged_at: str = None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO symptom_log (logged_at, body_zone, symptom, severity, allergen, note) VALUES (?, ?, ?, ?, ?, ?)",
        (logged_at or datetime.now().isoformat(timespec="minutes"), body_zone, symptom, severity, allergen, note),
    )
    conn.commit()
    conn.close()


def get_all_entries():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM symptom_log ORDER BY logged_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_entry(entry_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM symptom_log WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def get_setting(key: str, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM user_settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO user_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()
