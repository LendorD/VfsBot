"""Хендлеры команд ``/start`` и ``/help``.

Обе команды выводят справку по возможностям бота. ``/start`` дополнительно
приветствует пользователя.
"""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from loguru import logger

router = Router(name="start")

# Текст со списком всех команд (используется в /start и /help).
_COMMANDS_HELP = (
    "<b>Доступные команды:</b>\n\n"
    "/add — создать новую заявку на запись\n"
    "/status — посмотреть статус ваших заявок\n"
    "/edit — изменить существующую заявку\n"
    "/cancel — отменить активную заявку\n"
    "/help — показать эту справку"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Обработать команду ``/start``: приветствие и список команд.

    Args:
        message: Входящее сообщение с командой.
    """
    user = message.from_user
    logger.info("Команда /start от пользователя {}", user.id if user else "?")
    await message.answer(
        "👋 Здравствуйте! Я помогу отслеживать свободные слоты для записи в "
        "визовый центр VFS Global и автоматически бронировать подходящие.\n\n"
        f"{_COMMANDS_HELP}"
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Обработать команду ``/help``: краткая справка по командам.

    Args:
        message: Входящее сообщение с командой.
    """
    logger.debug("Команда /help")
    await message.answer(_COMMANDS_HELP)
