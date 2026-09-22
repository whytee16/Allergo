"""
Простая локальная авторизация (логин/регистрация) для дневника.
Пароли хранятся не в открытом виде — соль + SHA-256 (для MVP хакатона этого
достаточно; для продакшена — заменить на bcrypt/argon2 и добавить rate-limit).
"""
import hashlib
import os

from db import get_conn


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def register(username: str, password: str):
    username = username.strip()
    if not username or not password:
        return False, "Введите имя пользователя и пароль."
    if len(password) < 4:
        return False, "Пароль должен быть не короче 4 символов."

    conn = get_conn()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        return False, "Пользователь с таким именем уже существует."

    salt = os.urandom(8).hex()
    password_hash = _hash_password(password, salt)
    conn.execute(
        "INSERT INTO users (username, salt, password_hash, created_at) VALUES (?, ?, ?, datetime('now'))",
        (username, salt, password_hash),
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]
    conn.close()
    return True, user_id


def verify(username: str, password: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, salt, password_hash FROM users WHERE username = ?", (username.strip(),)
    ).fetchone()
    conn.close()
    if not row:
        return False, None
    if _hash_password(password, row["salt"]) == row["password_hash"]:
        return True, row["id"]
    return False, None
