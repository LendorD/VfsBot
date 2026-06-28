"""Хендлер команды ``/edit`` — изменение существующей заявки.

Сценарий:
    1. выбор заявки из списка активных;
    2. выбор поля для изменения (диапазон дат или конкретное поле);
    3. ввод нового значения с валидацией;
    4. сохранение и перезапуск поиска (статус -> waiting).
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from telegram_bot.keyboards import (
    APP_SELECT_PREFIX,
    EDIT_FIELD_PREFIX,
    EDITABLE_FIELDS,
    applications_keyboard,
    edit_fields_keyboard,
)
from telegram_bot.states import EditApplication
from storage.database import Database
from storage.models import ApplicationStatus
from core.exceptions import ApplicationNotFoundError, ValidationError
from core.validators import (
    parse_date,
    parse_date_range,
    validate_email,
    validate_latin_name,
    validate_passport,
    validate_phone,
)

router = Router(name="edit")


@router.message(Command("edit"))
async def cmd_edit(message: Message, state: FSMContext, db: Database) -> None:
    """Показать список активных заявок для редактирования.

    Args:
        message: Входящее сообщение с командой.
        state: Контекст FSM.
        db: Слой доступа к данным.
    """
    user = message.from_user
    logger.info("Команда /edit от пользователя {}", user.id if user else "?")

    applications = await db.get_user_applications(user.id, only_active=True)
    if not applications:
        await message.answer("У вас нет активных заявок для редактирования.")
        return

    await state.set_state(EditApplication.choosing_application)
    await message.answer(
        "Выберите заявку для редактирования:",
        reply_markup=applications_keyboard(applications, prefix=APP_SELECT_PREFIX),
    )


@router.callback_query(
    EditApplication.choosing_application, F.data.startswith(APP_SELECT_PREFIX)
)
async def choose_application(callback: CallbackQuery, state: FSMContext) -> None:
    """Запомнить выбранную заявку и предложить выбрать поле.

    Args:
        callback: Callback с идентификатором заявки.
        state: Контекст FSM.
    """
    application_id = int(callback.data.removeprefix(APP_SELECT_PREFIX))
    await state.update_data(application_id=application_id)
    await state.set_state(EditApplication.choosing_field)
    await callback.message.edit_text(
        f"Заявка №{application_id}. Что изменить?",
        reply_markup=edit_fields_keyboard(),
    )
    await callback.answer()


@router.callback_query(
    EditApplication.choosing_field, F.data.startswith(EDIT_FIELD_PREFIX)
)
async def choose_field(callback: CallbackQuery, state: FSMContext) -> None:
    """Запомнить выбранное поле и запросить новое значение.

    Args:
        callback: Callback с ключом поля.
        state: Контекст FSM.
    """
    field_key = callback.data.removeprefix(EDIT_FIELD_PREFIX)
    await state.update_data(field_key=field_key)
    await state.set_state(EditApplication.waiting_for_value)

    label = EDITABLE_FIELDS.get(field_key, field_key)
    prompt = _prompt_for_field(field_key, label)
    await callback.message.edit_text(prompt)
    await callback.answer()


@router.message(EditApplication.waiting_for_value)
async def process_value(message: Message, state: FSMContext, db: Database) -> None:
    """Провалидировать новое значение, сохранить и перезапустить поиск.

    Args:
        message: Сообщение с новым значением.
        state: Контекст FSM.
        db: Слой доступа к данным.
    """
    data = await state.get_data()
    field_key: str = data["field_key"]
    application_id: int = data["application_id"]

    try:
        update_fields = _validate_field(field_key, message.text or "")
    except ValidationError as exc:
        await message.answer(f"❌ {exc}\nПопробуйте ещё раз.")
        return

    # При любом изменении перезапускаем поиск: статус -> waiting.
    update_fields["status"] = ApplicationStatus.WAITING

    try:
        await db.update_application(application_id, **update_fields)
    except ApplicationNotFoundError:
        await state.clear()
        await message.answer("Заявка не найдена. Возможно, она была отменена.")
        return

    await state.clear()
    logger.info("Заявка №{} отредактирована (поле {})", application_id, field_key)
    await message.answer(
        f"✅ Заявка №{application_id} обновлена. Поиск перезапущен."
    )


def _prompt_for_field(field_key: str, label: str) -> str:
    """Сформировать приглашение к вводу значения для поля.

    Args:
        field_key: Ключ редактируемого поля.
        label: Человекочитаемое название поля.

    Returns:
        str: Текст приглашения.
    """
    if field_key == "dates":
        return (
            "📅 Введите новый диапазон дат в формате "
            "<code>ДД.ММ.ГГГГ-ДД.ММ.ГГГГ</code>:"
        )
    if field_key in {"birth_date", "passport_issue_date", "passport_expiry_date"}:
        return f"Введите новое значение «{label}» в формате ДД.ММ.ГГГГ:"
    return f"Введите новое значение «{label}»:"


def _validate_field(field_key: str, raw: str) -> dict:
    """Провалидировать значение поля и вернуть словарь для обновления.

    Args:
        field_key: Ключ редактируемого поля.
        raw: Сырое значение из сообщения пользователя.

    Returns:
        dict: Пары «поле модели -> значение» для записи в БД.

    Raises:
        ValidationError: Если значение некорректно.
    """
    if field_key == "dates":
        start_date, end_date = parse_date_range(raw)
        return {"start_date": start_date, "end_date": end_date}

    if field_key == "surname":
        return {"surname": validate_latin_name(raw, "Фамилия")}

    if field_key == "name":
        return {"name": validate_latin_name(raw, "Имя")}

    if field_key == "birth_date":
        return {"birth_date": parse_date(raw, allow_past=True)}

    if field_key == "passport_number":
        return {"passport_number": validate_passport(raw)}

    if field_key == "passport_issue_date":
        return {"passport_issue_date": parse_date(raw, allow_past=True)}

    if field_key == "passport_expiry_date":
        return {"passport_expiry_date": parse_date(raw, allow_past=False)}

    if field_key == "email":
        return {"email": validate_email(raw)}

    if field_key == "phone":
        return {"phone": validate_phone(raw)}

    raise ValidationError(f"Неизвестное поле для редактирования: {field_key}")
