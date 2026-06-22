"""Хендлер команды ``/status`` — просмотр статуса всех заявок пользователя."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

from storage.database import Database
from storage.models import Application, ApplicationStatus, STATUS_LABELS_RU

router = Router(name="status")


@router.message(Command("status"))
async def cmd_status(message: Message, db: Database) -> None:
    """Показать список заявок пользователя с их статусами.

    Args:
        message: Входящее сообщение с командой.
        db: Слой доступа к данным (внедряется диспетчером).
    """
    user = message.from_user
    logger.info("Команда /status от пользователя {}", user.id if user else "?")

    applications = await db.get_user_applications(user.id)
    if not applications:
        await message.answer(
            "У вас пока нет заявок. Создайте новую командой /add."
        )
        return

    blocks = [_format_application(app) for app in applications]
    await message.answer("\n\n".join(blocks))


def _format_application(app: Application) -> str:
    """Сформировать текстовое описание одной заявки.

    Args:
        app: Заявка пользователя.

    Returns:
        str: HTML-блок с данными заявки.
    """
    status_label = STATUS_LABELS_RU.get(app.status, app.status.value)
    lines = [
        f"<b>Заявка №{app.id}</b>",
        f"📅 Диапазон: {app.start_date.strftime('%d.%m.%Y')} – "
        f"{app.end_date.strftime('%d.%m.%Y')}",
        f"📌 Статус: {status_label}",
    ]

    # Для выполненной записи показываем реквизиты бронирования.
    if app.status == ApplicationStatus.BOOKED:
        lines.append(
            f"✅ Запись: {app.booked_date.strftime('%d.%m.%Y')} "
            f"в {app.booked_time}"
        )
        if app.booking_reference:
            lines.append(f"🔖 Номер брони: {app.booking_reference}")

    return "\n".join(lines)
