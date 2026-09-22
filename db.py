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
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS symptom_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
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
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            PRIMARY KEY (user_id, key)
        )
        """
    )
    conn.commit()
    conn.close()

def add_entry(user_id: int, body_zone: str, symptom: str, severity: int,
              allergen: str, note: str = "", logged_at: str = None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO symptom_log (user_id, logged_at, body_zone, symptom, severity, allergen, note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, logged_at or datetime.now().isoformat(timespec="minutes"),
         body_zone, symptom, severity, allergen, note),
    )
    conn.commit()
    conn.close()


def get_all_entries(user_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM symptom_log WHERE user_id = ? ORDER BY logged_at DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_entry(user_id: int, entry_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM symptom_log WHERE id = ? AND user_id = ?", (entry_id, user_id))
    conn.commit()
    conn.close()


def get_setting(user_id: int, key: str, default=None):
    conn = get_conn()
    row = conn.execute(
        "SELECT value FROM user_settings WHERE user_id = ? AND key = ?", (user_id, key)
    ).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(user_id: int, key: str, value: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO user_settings (user_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
        (user_id, key, value),
    )
    conn.commit()
    conn.close()
