"""Хранилище веб-сайта: пользователи и заявки (SQLite + SQLAlchemy).

Сайт использует собственную базу SQLite (отдельно от PostgreSQL бота), чтобы
его можно было запускать независимо. Когда движок бронирования будет подключён,
он будет читать заявки из этой же таблицы (или они будут синхронизированы).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from sqlalchemy import ForeignKey, String, Text, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "webapp.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Базовый класс моделей."""


class User(Base):
    """Пользователь сайта."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    salt: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Task(Base):
    """Заявка на запись (одна задача бронирования)."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # Сайт записи (на будущее — поддержка разных визовых порталов).
    site: Mapped[str] = mapped_column(String(50), default="vfs_fr")

    center: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(255), default="")
    subcategory: Mapped[str] = mapped_column(String(255), default="")

    date_start: Mapped[str] = mapped_column(String(20), default="")
    date_end: Mapped[str] = mapped_column(String(20), default="")

    # Список заявителей хранится как JSON (любое число заявителей).
    applicants_json: Mapped[str] = mapped_column(Text, default="[]")

    auto_pay: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(30), default="created")
    created_at: Mapped[dt.datetime] = mapped_column(default=dt.datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="tasks")

    @property
    def applicants(self) -> list[dict]:
        """Разобрать список заявителей из JSON."""
        try:
            return json.loads(self.applicants_json or "[]")
        except json.JSONDecodeError:
            return []

    @property
    def applicants_count(self) -> int:
        """Число заявителей в заявке."""
        return len(self.applicants)


def init_db() -> None:
    """Создать таблицы, если их ещё нет."""
    Base.metadata.create_all(engine)
