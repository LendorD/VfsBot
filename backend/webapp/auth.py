"""Аутентификация сайта: хеширование паролей и текущий пользователь.

Пароли хранятся как PBKDF2-HMAC-SHA256 с индивидуальной солью (без внешних
зависимостей). Сессия — подписанная cookie (Starlette SessionMiddleware),
в ней лежит только ``user_id``.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from webapp.db import User

_ITERATIONS = 200_000


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Захешировать пароль. Возвращает (salt_hex, hash_hex)."""
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS
    )
    return salt, digest.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Проверить пароль против сохранённого хеша (constant-time)."""
    _, actual = hash_password(password, salt)
    return hmac.compare_digest(actual, expected_hash)


def get_user_by_email(db: Session, email: str) -> User | None:
    """Найти пользователя по email (без учёта регистра)."""
    normalized = email.strip().lower()
    return db.scalar(select(User).where(User.email == normalized))


def create_user(db: Session, email: str, password: str) -> User:
    """Создать пользователя с захешированным паролем."""
    salt, password_hash = hash_password(password)
    user = User(
        email=email.strip().lower(), salt=salt, password_hash=password_hash
    )
    db.add(user)
    db.commit()
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    """Вернуть пользователя при верных учётных данных, иначе None."""
    user = get_user_by_email(db, email)
    if user and verify_password(password, user.salt, user.password_hash):
        return user
    return None
