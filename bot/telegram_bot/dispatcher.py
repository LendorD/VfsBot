"""Настройка бота и диспетчера aiogram.

Содержит фабрики создания объектов :class:`Bot` и :class:`Dispatcher`,
регистрацию роутеров-хендлеров, внедрение зависимостей (БД) и установку
меню команд.
"""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from loguru import logger

from telegram_bot.handlers import routers
from storage.database import Database

# Список команд для меню Telegram (кнопка «/» в интерфейсе).
_BOT_COMMANDS = [
    BotCommand(command="start", description="Приветствие и список команд"),
    BotCommand(command="add", description="Создать заявку на запись"),
    BotCommand(command="status", description="Статус ваших заявок"),
    BotCommand(command="edit", description="Изменить заявку"),
    BotCommand(command="cancel", description="Отменить заявку"),
    BotCommand(command="help", description="Справка по командам"),
]


def create_bot(token: str) -> Bot:
    """Создать экземпляр бота с HTML-разметкой по умолчанию.

    Args:
        token: Токен Telegram-бота.

    Returns:
        Bot: Готовый экземпляр бота.
    """
    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(database: Database) -> Dispatcher:
    """Создать диспетчер, зарегистрировать роутеры и внедрить зависимости.

    База данных передаётся в ``workflow_data`` диспетчера и автоматически
    прокидывается в хендлеры, объявившие параметр ``db: Database``.

    Args:
        database: Слой доступа к данным.

    Returns:
        Dispatcher: Настроенный диспетчер.
    """
    dispatcher = Dispatcher(storage=MemoryStorage())
    # Внедрение зависимости: хендлеры получат её как параметр `db`.
    dispatcher["db"] = database

    for router in routers:
        dispatcher.include_router(router)

    logger.info("Диспетчер настроен, зарегистрировано {} роутеров", len(routers))
    return dispatcher


async def setup_bot_commands(bot: Bot) -> None:
    """Установить меню команд бота в интерфейсе Telegram.

    Args:
        bot: Экземпляр бота.
    """
    await bot.set_my_commands(_BOT_COMMANDS)
    logger.info("Меню команд бота установлено")
