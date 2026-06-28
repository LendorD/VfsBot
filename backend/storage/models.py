"""SQLAlchemy-модели приложения (декларативный стиль 2.0).

Описывает три таблицы:
    * ``users``        — пользователи Telegram;
    * ``applications`` — заявки на запись с персональными данными;
    * ``sessions``     — сохранённые сессии браузера (cookies, localStorage).

Для Telegram ID используется ``BigInteger``, так как идентификаторы могут
превышать диапазон 32-битного целого.
"""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    """Базовый декларативный класс для всех моделей."""


class ApplicationStatus(str, enum.Enum):
    """Возможные статусы заявки на запись.

    Наследование от ``str`` упрощает сериализацию и сравнение со строками.
    """

    WAITING = "waiting"      # ожидание начала поиска
    SEARCHING = "searching"  # идёт поиск слотов
    FOUND = "found"          # слот найден, выполняется бронирование
    BOOKED = "booked"        # запись успешно выполнена
    ERROR = "error"          # произошла ошибка
    CANCELLED = "cancelled"  # заявка отменена пользователем


# Человекочитаемые названия статусов на русском (для сообщений бота).
STATUS_LABELS_RU: dict[ApplicationStatus, str] = {
    ApplicationStatus.WAITING: "ожидание",
    ApplicationStatus.SEARCHING: "поиск",
    ApplicationStatus.FOUND: "запись найдена",
    ApplicationStatus.BOOKED: "запись выполнена",
    ApplicationStatus.ERROR: "ошибка",
    ApplicationStatus.CANCELLED: "отменена",
}


class User(Base):
    """Пользователь Telegram, создавший заявки.

    Attributes:
        id: Внутренний первичный ключ.
        telegram_id: Уникальный идентификатор пользователя в Telegram.
        username: Username пользователя (может отсутствовать).
        created_at: Время создания записи.
        applications: Связанные заявки пользователя.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    applications: Mapped[list["Application"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Application(Base):
    """Заявка на запись в визовый центр VFS Global.

    Хранит диапазон желаемых дат, персональные данные заявителя, текущий
    статус и (после успешной записи) реквизиты бронирования.

    Attributes:
        id: Первичный ключ — отображается пользователю как «номер заявки».
        user_id: Внешний ключ на пользователя.
        start_date: Начало диапазона дат поиска.
        end_date: Конец диапазона дат поиска.
        status: Текущий статус заявки.
        surname: Фамилия латиницей.
        name: Имя латиницей.
        birth_date: Дата рождения.
        passport_number: Номер паспорта.
        passport_issue_date: Дата выдачи паспорта.
        passport_expiry_date: Дата окончания срока действия паспорта.
        email: Контактный email.
        phone: Контактный телефон (международный формат).
        booked_date: Дата найденной записи (если есть).
        booked_time: Время найденной записи (если есть).
        booking_reference: Номер бронирования (если есть).
        created_at: Время создания заявки.
        updated_at: Время последнего обновления заявки.
    """

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # --- Диапазон дат поиска ---
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # --- Статус заявки ---
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status"),
        default=ApplicationStatus.WAITING,
        nullable=False,
        index=True,
    )

    # --- Персональные данные заявителя ---
    surname: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    passport_number: Mapped[str] = mapped_column(String(32), nullable=False)
    passport_issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    passport_expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)

    # --- Данные о найденной записи ---
    booked_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    booked_time: Mapped[str | None] = mapped_column(String(16), nullable=True)
    booking_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- Служебные поля ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="applications")

    def __repr__(self) -> str:  # noqa: D105 - служебное представление
        return (
            f"<Application id={self.id} status={self.status.value} "
            f"{self.start_date}..{self.end_date}>"
        )


class Session(Base):
    """Сохранённое состояние браузерной сессии VFS.

    Позволяет переиспользовать cookies и localStorage между запусками,
    чтобы не проходить авторизацию и капчу заново.

    Attributes:
        id: Первичный ключ.
        cookies: Cookies браузера в формате JSON.
        local_storage: Содержимое localStorage в формате JSON.
        created_at: Время создания сессии.
        expires_at: Предполагаемое время истечения сессии.
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    cookies: Mapped[list | dict] = mapped_column(JSONB, nullable=False)
    local_storage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
