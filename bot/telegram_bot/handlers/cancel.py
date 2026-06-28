"""Хендлер команды ``/cancel`` — отмена активной заявки.

Сценарий:
    1. показать список активных заявок с inline-кнопками;
    2. по нажатию — удалить заявку из БД и остановить её обработку.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from loguru import logger

from telegram_bot.keyboards import CANCEL_APP_PREFIX, applications_keyboard
from storage.database import Database
from core.exceptions import ApplicationNotFoundError

router = Router(name="cancel")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, db: Database) -> None:
    """Показать список активных заявок для отмены.

    Args:
        message: Входящее сообщение с командой.
        db: Слой доступа к данным.
    """
    user = message.from_user
    logger.info("Команда /cancel от пользователя {}", user.id if user else "?")

    applications = await db.get_user_applications(user.id, only_active=True)
    if not applications:
        await message.answer("У вас нет активных заявок для отмены.")
        return

    await message.answer(
        "Выберите заявку для отмены:",
        reply_markup=applications_keyboard(applications, prefix=CANCEL_APP_PREFIX),
    )


@router.callback_query(F.data.startswith(CANCEL_APP_PREFIX))
async def process_cancel(callback: CallbackQuery, db: Database) -> None:
    """Удалить выбранную заявку и подтвердить отмену.

    Args:
        callback: Callback с идентификатором заявки.
        db: Слой доступа к данным.
    """
    application_id = int(callback.data.removeprefix(CANCEL_APP_PREFIX))
    try:
        await db.delete_application(application_id)
    except ApplicationNotFoundError:
        await callback.message.edit_text("Заявка уже удалена или не найдена.")
        await callback.answer()
        return

    logger.info("Заявка №{} отменена пользователем {}",
                application_id, callback.from_user.id)
    await callback.message.edit_text(f"❌ Заявка №{application_id} отменена.")
    await callback.answer()
