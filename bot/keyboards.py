"""Inline-клавиатуры бота.

Содержит фабрики клавиатур для подтверждения данных, выбора заявки и
выбора редактируемого поля. Callback-данные кодируются простыми строками
с префиксами, что упрощает их разбор в хендлерах.
"""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from storage.models import Application

# --- Префиксы callback-данных ---
CONFIRM_YES = "confirm:yes"
CONFIRM_NO = "confirm:no"
APP_SELECT_PREFIX = "app:"        # выбор заявки: app:<id>
EDIT_FIELD_PREFIX = "field:"      # выбор поля: field:<key>
CANCEL_APP_PREFIX = "cancel:"     # отмена заявки: cancel:<id>

# Поля заявки, доступные для редактирования: ключ -> человекочитаемое имя.
EDITABLE_FIELDS: dict[str, str] = {
    "dates": "Диапазон дат",
    "surname": "Фамилия",
    "name": "Имя",
    "birth_date": "Дата рождения",
    "passport_number": "Номер паспорта",
    "passport_issue_date": "Дата выдачи паспорта",
    "passport_expiry_date": "Дата окончания паспорта",
    "email": "Email",
    "phone": "Телефон",
}


def confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения данных заявки.

    Returns:
        Клавиатура с кнопками «Подтвердить» и «Отменить».
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=CONFIRM_YES)
    builder.button(text="❌ Отменить", callback_data=CONFIRM_NO)
    builder.adjust(2)
    return builder.as_markup()


def applications_keyboard(
    applications: Sequence[Application], prefix: str = APP_SELECT_PREFIX
) -> InlineKeyboardMarkup:
    """Клавиатура выбора заявки из списка.

    Args:
        applications: Список заявок пользователя.
        prefix: Префикс callback-данных (выбор или отмена).

    Returns:
        Клавиатура с одной кнопкой на заявку.
    """
    builder = InlineKeyboardBuilder()
    for app in applications:
        builder.button(
            text=(
                f"№{app.id} | "
                f"{app.start_date.strftime('%d.%m.%Y')}–"
                f"{app.end_date.strftime('%d.%m.%Y')}"
            ),
            callback_data=f"{prefix}{app.id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def edit_fields_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора поля для редактирования.

    Returns:
        Клавиатура с кнопкой на каждое редактируемое поле.
    """
    builder = InlineKeyboardBuilder()
    for key, label in EDITABLE_FIELDS.items():
        builder.button(text=label, callback_data=f"{EDIT_FIELD_PREFIX}{key}")
    builder.adjust(2)
    return builder.as_markup()


def _button(text: str, data: str) -> InlineKeyboardButton:
    """Вспомогательная фабрика inline-кнопки.

    Args:
        text: Подпись кнопки.
        data: Callback-данные.

    Returns:
        Готовая кнопка.
    """
    return InlineKeyboardButton(text=text, callback_data=data)
