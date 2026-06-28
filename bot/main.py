"""Точка входа приложения.

Инициализирует все компоненты в правильном порядке и запускает бота:
    1. логгер и настройки;
    2. база данных (создание таблиц);
    3. браузер (Playwright) и клиент VFS;
    4. планировщик проверки слотов;
    5. бот и диспетчер (long polling).

Корректно освобождает ресурсы при остановке (Ctrl+C / SIGTERM).
"""

from __future__ import annotations

import asyncio

from aiogram import Bot
from loguru import logger

from telegram_bot.dispatcher import create_bot, create_dispatcher, setup_bot_commands
from captcha.solver import get_captcha_solver
from vfs_site.client import VFSClient
from vfs_site.browser import BrowserManager
from scheduler.checker import SlotChecker
from storage.database import Database
from core.config import get_settings
from core.logger import setup_logger


def make_notifier(bot: Bot):
    """Создать функцию-уведомитель, отправляющую сообщения через бота.

    Args:
        bot: Экземпляр бота.

    Returns:
        Корутину ``notify(telegram_id, text)`` для планировщика.
    """

    async def notify(telegram_id: int, text: str) -> None:
        """Отправить пользователю текстовое уведомление.

        Args:
            telegram_id: Идентификатор получателя.
            text: Текст сообщения.
        """
        await bot.send_message(chat_id=telegram_id, text=text)

    return notify


async def main() -> None:
    """Запустить приложение и блокироваться на polling до остановки."""
    setup_logger()
    settings = get_settings()
    logger.info("Запуск приложения VFS-бота")

    # --- База данных ---
    database = Database(settings.database_url)
    await database.create_tables()

    # --- Браузер и клиент VFS ---
    browser_manager = BrowserManager()
    await browser_manager.start()
    captcha_solver = get_captcha_solver(settings.captcha_api_key)
    vfs_client = VFSClient(browser_manager, captcha_solver)

    # --- Бот и диспетчер ---
    if not settings.bot_token:
        raise RuntimeError(
            "BOT_TOKEN не задан в .env — он обязателен для запуска бота. "
            "Для автономной проверки слотов без бота используйте run_check.py."
        )
    bot = create_bot(settings.bot_token)
    dispatcher = create_dispatcher(database)
    await setup_bot_commands(bot)

    # --- Планировщик ---
    scheduler = SlotChecker(
        database=database,
        vfs_client=vfs_client,
        notifier=make_notifier(bot),
    )
    scheduler.start()

    # --- Запуск long polling ---
    try:
        logger.info("Бот запущен, начинаю получать обновления")
        await dispatcher.start_polling(bot)
    finally:
        # Корректное освобождение ресурсов при остановке.
        logger.info("Остановка приложения, освобождаю ресурсы")
        scheduler.shutdown()
        await browser_manager.stop()
        await database.dispose()
        await bot.session.close()
        logger.info("Приложение остановлено")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки")
