"""Хендлер команды ``/add`` — пошаговый сбор данных заявки через FSM.

Сценарий:
    1. запрос диапазона дат;
    2. последовательный сбор персональных данных с валидацией каждого поля;
    3. показ сводки с inline-кнопками подтверждения;
    4. сохранение заявки в БД при подтверждении.
"""

from __future__ import annotations

from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from bot.keyboards import CONFIRM_NO, CONFIRM_YES, confirmation_keyboard
from bot.states import AddApplication
from storage.database import Database
from utils.exceptions import ValidationError
from utils.validators import (
    parse_date,
    parse_date_range,
    validate_email,
    validate_latin_name,
    validate_passport,
    validate_phone,
)

router = Router(name="add")


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    """Начать сценарий создания заявки: запросить диапазон дат.

    Args:
        message: Входящее сообщение с командой.
        state: Контекст FSM пользователя.
    """
    logger.info("Команда /add от пользователя {}",
                message.from_user.id if message.from_user else "?")
    await state.set_state(AddApplication.waiting_for_dates)
    await message.answer(
        "📅 Введите желаемый диапазон дат для записи в формате:\n"
        "<code>ДД.ММ.ГГГГ-ДД.ММ.ГГГГ</code>\n\n"
        "Например: <code>01.07.2026-15.07.2026</code>"
    )


@router.message(AddApplication.waiting_for_dates)
async def process_dates(message: Message, state: FSMContext) -> None:
    """Принять и проверить диапазон дат, затем запросить фамилию.

    Args:
        message: Сообщение с диапазоном дат.
        state: Контекст FSM.
    """
    try:
        start_date, end_date = parse_date_range(message.text or "")
    except ValidationError as exc:
        await message.answer(f"❌ {exc}\nПопробуйте ещё раз.")
        return

    await state.update_data(start_date=start_date, end_date=end_date)
    await state.set_state(AddApplication.waiting_for_surname)
    await message.answer("👤 Введите <b>фамилию латиницей</b> (как в паспорте):")


@router.message(AddApplication.waiting_for_surname)
async def process_surname(message: Message, state: FSMContext) -> None:
    """Принять фамилию и запросить имя."""
    try:
        surname = validate_latin_name(message.text or "", "Фамилия")
    except ValidationError as exc:
        await message.answer(f"❌ {exc}\nПопробуйте ещё раз.")
        return

    await state.update_data(surname=surname)
    await state.set_state(AddApplication.waiting_for_name)
    await message.answer("👤 Введите <b>имя латиницей</b> (как в паспорте):")


@router.message(AddApplication.waiting_for_name)
async def process_name(message: Message, state: FSMContext) -> None:
    """Принять имя и запросить дату рождения."""
    try:
        name = validate_latin_name(message.text or "", "Имя")
    except ValidationError as exc:
        await message.answer(f"❌ {exc}\nПопробуйте ещё раз.")
        return

    await state.update_data(name=name)
    await state.set_state(AddApplication.waiting_for_birth_date)
    await message.answer("🎂 Введите <b>дату рождения</b> (ДД.ММ.ГГГГ):")


@router.message(AddApplication.waiting_for_birth_date)
async def process_birth_date(message: Message, state: FSMContext) -> None:
    """Принять дату рождения и запросить номер паспорта."""
    try:
        birth_date = parse_date(message.text or "", allow_past=True)
    except ValidationError as exc:
        await message.answer(f"❌ {exc}\nПопробуйте ещё раз.")
        return

    await state.update_data(birth_date=birth_date)
    await state.set_state(AddApplication.waiting_for_passport)
    await message.answer("🛂 Введите <b>номер паспорта</b>:")


@router.message(AddApplication.waiting_for_passport)
async def process_passport(message: Message, state: FSMContext) -> None:
    """Принять номер паспорта и запросить дату выдачи."""
    try:
        passport = validate_passport(message.text or "")
    except ValidationError as exc:
        await message.answer(f"❌ {exc}\nПопробуйте ещё раз.")
        return

    await state.update_data(passport_number=passport)
    await state.set_state(AddApplication.waiting_for_passport_issue)
    await message.answer("📄 Введите <b>дату выдачи паспорта</b> (ДД.ММ.ГГГГ):")


@router.message(AddApplication.waiting_for_passport_issue)
async def process_passport_issue(message: Message, state: FSMContext) -> None:
    """Принять дату выдачи паспорта и запросить дату окончания."""
    try:
        issue_date = parse_date(message.text or "", allow_past=True)
    except ValidationError as exc:
        await message.answer(f"❌ {exc}\nПопробуйте ещё раз.")
        return

    await state.update_data(passport_issue_date=issue_date)
    await state.set_state(AddApplication.waiting_for_passport_expiry)
    await message.answer(
        "📄 Введите <b>дату окончания паспорта</b> (ДД.ММ.ГГГГ):"
    )


@router.message(AddApplication.waiting_for_passport_expiry)
async def process_passport_expiry(message: Message, state: FSMContext) -> None:
    """Принять дату окончания паспорта (должна быть в будущем)."""
    try:
        # Паспорт должен быть действующим — дата окончания не в прошлом.
        expiry_date = parse_date(message.text or "", allow_past=False)
    except ValidationError as exc:
        await message.answer(f"❌ {exc}\nПопробуйте ещё раз.")
        return

    data = await state.get_data()
    issue_date: date = data["passport_issue_date"]
    if expiry_date <= issue_date:
        await message.answer(
            "❌ Дата окончания паспорта должна быть позже даты выдачи. "
            "Попробуйте ещё раз."
        )
        return

    await state.update_data(passport_expiry_date=expiry_date)
    await state.set_state(AddApplication.waiting_for_email)
    await message.answer("✉️ Введите <b>email</b>:")


@router.message(AddApplication.waiting_for_email)
async def process_email(message: Message, state: FSMContext) -> None:
    """Принять email и запросить телефон."""
    try:
        email = validate_email(message.text or "")
    except ValidationError as exc:
        await message.answer(f"❌ {exc}\nПопробуйте ещё раз.")
        return

    await state.update_data(email=email)
    await state.set_state(AddApplication.waiting_for_phone)
    await message.answer(
        "📞 Введите <b>номер телефона</b> в международном формате "
        "(например, +79991234567):"
    )


@router.message(AddApplication.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    """Принять телефон и показать сводку для подтверждения."""
    try:
        phone = validate_phone(message.text or "")
    except ValidationError as exc:
        await message.answer(f"❌ {exc}\nПопробуйте ещё раз.")
        return

    await state.update_data(phone=phone)
    await state.set_state(AddApplication.confirmation)

    data = await state.get_data()
    await message.answer(
        _format_summary(data),
        reply_markup=confirmation_keyboard(),
    )


@router.callback_query(AddApplication.confirmation, F.data == CONFIRM_YES)
async def confirm_yes(
    callback: CallbackQuery, state: FSMContext, db: Database
) -> None:
    """Сохранить заявку в БД после подтверждения пользователем.

    Args:
        callback: Callback от нажатия кнопки «Подтвердить».
        state: Контекст FSM.
        db: Слой доступа к данным (внедряется диспетчером).
    """
    data = await state.get_data()
    await state.clear()

    user = callback.from_user
    application = await db.create_application(
        telegram_id=user.id,
        username=user.username,
        data=data,
    )
    logger.info("Пользователь {} создал заявку №{}", user.id, application.id)

    await callback.message.edit_text(
        f"✅ Заявка №{application.id} создана. Начинаю поиск свободных слотов "
        f"с {application.start_date.strftime('%d.%m.%Y')} по "
        f"{application.end_date.strftime('%d.%m.%Y')}."
    )
    await callback.answer()


@router.callback_query(AddApplication.confirmation, F.data == CONFIRM_NO)
async def confirm_no(callback: CallbackQuery, state: FSMContext) -> None:
    """Отменить создание заявки на шаге подтверждения.

    Args:
        callback: Callback от нажатия кнопки «Отменить».
        state: Контекст FSM.
    """
    await state.clear()
    await callback.message.edit_text(
        "❌ Создание заявки отменено. Чтобы начать заново, отправьте /add."
    )
    await callback.answer()


def _format_summary(data: dict) -> str:
    """Сформировать текст сводки введённых данных.

    Args:
        data: Накопленные в FSM данные заявки.

    Returns:
        str: HTML-текст со всеми полями для подтверждения.
    """
    return (
        "<b>Проверьте введённые данные:</b>\n\n"
        f"📅 Диапазон дат: {data['start_date'].strftime('%d.%m.%Y')} – "
        f"{data['end_date'].strftime('%d.%m.%Y')}\n"
        f"👤 Фамилия: {data['surname']}\n"
        f"👤 Имя: {data['name']}\n"
        f"🎂 Дата рождения: {data['birth_date'].strftime('%d.%m.%Y')}\n"
        f"🛂 Паспорт: {data['passport_number']}\n"
        f"📄 Выдан: {data['passport_issue_date'].strftime('%d.%m.%Y')}\n"
        f"📄 Действует до: {data['passport_expiry_date'].strftime('%d.%m.%Y')}\n"
        f"✉️ Email: {data['email']}\n"
        f"📞 Телефон: {data['phone']}\n\n"
        "Всё верно?"
    )
