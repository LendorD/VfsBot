"""Схема задачи бронирования — единый формат для бота, сайта и движка.

Эти модели не зависят ни от Telegram, ни от веб-формы, ни от Playwright.
И Telegram-бот, и будущий веб-бэкенд собирают одинаковый :class:`BookingTask`,
а движок бронирования (:mod:`vfs_site.booking_flow`) его исполняет.

Поля заявителя соответствуют форме шага 2 на сайте VFS («Информация о Вас»).
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


def to_site_date(value: date) -> str:
    """Преобразовать дату в формат сайта VFS — ``ДД/ММ/ГГГГ``."""
    return value.strftime("%d/%m/%Y")


class Gender(str, Enum):
    """Пол заявителя (значения как в выпадающем списке сайта)."""

    MALE = "Мужской"
    FEMALE = "Женский"


class ApplicantData(BaseModel):
    """Данные одного заявителя (форма «Информация о Вас»)."""

    first_name: str = Field(..., description="Имя (латиницей, как в паспорте)")
    surname: str = Field(..., description="Фамилия (латиницей)")
    gender: Gender = Field(..., description="Пол")
    birth_date: date = Field(..., description="Дата рождения")
    nationality: str = Field(..., description="Текущее гражданство (как на сайте)")
    passport_number: str = Field(..., description="Номер паспорта")
    passport_expiry: date = Field(..., description="Срок действия паспорта")
    phone_code: str = Field(default="7", description="Код страны телефона")
    phone: str = Field(..., description="Контактный номер без кода")
    email: str = Field(..., description="Электронная почта")


class BookingCriteria(BaseModel):
    """Критерии записи (шаг 1). Текст как на сайте; частичное совпадение ок."""

    center: str = Field(..., description="Центр приложений")
    category: str = Field(..., description="Категория записи")
    subcategory: str = Field(..., description="Подкатегория")


class BookingTask(BaseModel):
    """Полная задача бронирования.

    Attributes:
        criteria: Что выбирать на шаге 1.
        applicants: Список заявителей (минимум один; число не ограничено).
        date_start: Нижняя граница желаемого диапазона дат (включительно).
        date_end: Верхняя граница желаемого диапазона дат (включительно).
        auto_pay: Доводить ли бронирование до фактической ОПЛАТЫ автоматически.
            ВНИМАНИЕ: True означает реальное списание средств без подтверждения.
    """

    criteria: BookingCriteria
    applicants: list[ApplicantData] = Field(..., min_length=1)
    date_start: date | None = Field(default=None)
    date_end: date | None = Field(default=None)
    auto_pay: bool = Field(default=False)

    @property
    def applicants_count(self) -> int:
        """Число заявителей в задаче."""
        return len(self.applicants)
