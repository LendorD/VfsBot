"""Настройка структурированного логирования на базе loguru.

Логи выводятся одновременно в консоль (цветной формат) и в файл с
ротацией. Формат сообщений — на русском, с указанием модуля, функции и
строки, что упрощает отладку бизнес-логики.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from core.config import get_settings

# Формат записи лога: время | уровень | модуль:функция:строка | сообщение
_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)


def setup_logger() -> "logger.__class__":
    """Сконфигурировать глобальный логгер loguru.

    Удаляет стандартный обработчик и добавляет два новых: вывод в stderr и
    запись в файл с ротацией и сжатием. Уровень и путь берутся из настроек.

    Returns:
        Объект логгера loguru, готовый к использованию.
    """
    settings = get_settings()

    # Сбрасываем обработчики по умолчанию, чтобы избежать дублирования.
    logger.remove()

    # Вывод в консоль.
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=_LOG_FORMAT,
        colorize=True,
        backtrace=True,
        diagnose=False,  # Не выводим значения переменных (персональные данные!).
    )

    # Запись в файл с ротацией.
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_path,
        level=settings.log_level,
        format=_LOG_FORMAT,
        rotation="10 MB",       # Новый файл при достижении 10 МБ.
        retention="14 days",    # Хранить логи 14 дней.
        compression="zip",      # Архивировать старые файлы.
        encoding="utf-8",
        enqueue=True,           # Потокобезопасная запись (для async).
        backtrace=True,
        diagnose=False,
    )

    logger.info("Логгер инициализирован (уровень: {})", settings.log_level)
    return logger
