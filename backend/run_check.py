"""Автономная проверка слотов VFS без Telegram-бота.

Запускает только браузерный слой (BrowserManager + VFSClient) и пытается
найти свободный слот в заданном диапазоне дат. Не требует ни Telegram-бота,
ни PostgreSQL — удобно для отладки парсинга сайта. Telegram-бота можно
подключить позже: он использует те же модули.

Запуск:
    python run_check.py 01.07.2026 15.07.2026

Опции:
    --headful   запустить браузер с видимым окном (перекрывает BROWSER_HEADLESS)
"""

from __future__ import annotations

import argparse
import asyncio

from loguru import logger

from captcha.solver import get_captcha_solver
from vfs_site.client import VFSClient
from vfs_site.browser import BrowserManager
from core.config import get_settings
from core.logger import setup_logger
from core.validators import parse_date_range
from core.exceptions import ValidationError, VFSBotError


async def run(date_range: str, headful: bool = False) -> int:
    """Выполнить одну проверку слотов и вывести результат.

    Args:
        date_range: Диапазон дат в формате ``ДД.ММ.ГГГГ-ДД.ММ.ГГГГ``.
        headful: Показать окно браузера во время проверки (для отладки).
            Чтобы открыть страницу и оставить окно открытым для подбора
            селекторов, используйте отдельный скрипт ``inspect_page.py``.

    Returns:
        int: Код возврата процесса (0 — успех, 1 — ошибка/каркас).
    """
    setup_logger()
    settings = get_settings()

    try:
        start_date, end_date = parse_date_range(date_range)
    except ValidationError as exc:
        logger.error("Некорректный диапазон дат: {}", exc)
        print(f"Ошибка в датах: {exc}")
        return 1

    logger.info("Автономная проверка слотов: {} — {}", start_date, end_date)

    browser_manager = BrowserManager()
    # headful=True перекрывает BROWSER_HEADLESS из .env.
    await browser_manager.start(headless=False if headful else None)
    try:
        captcha_solver = get_captcha_solver(settings.captcha_api_key)
        client = VFSClient(browser_manager, captcha_solver)
        slot = await client.find_slot(start_date, end_date)

        if slot is None:
            logger.info("Свободных слотов в диапазоне не найдено")
            print("Свободных слотов в диапазоне не найдено.")
            return 0

        logger.info("Найден слот: {} {}", slot.slot_date, slot.slot_time)
        print(
            f"Найден слот: {slot.slot_date.strftime('%d.%m.%Y')} "
            f"{slot.slot_time}"
        )
        return 0

    except VFSBotError as exc:
        # Сейчас браузерный клиент — каркас, поэтому ожидаемо попадаем сюда.
        logger.warning("Проверка не завершена: {}", exc)
        print(
            "Проверка не завершена (браузерный клиент VFS пока не реализован).\n"
            f"Причина: {exc}"
        )
        return 1
    finally:
        await browser_manager.stop()


def main() -> None:
    """Разобрать аргументы командной строки и запустить проверку."""
    parser = argparse.ArgumentParser(
        description="Автономная проверка свободных слотов VFS без Telegram-бота",
    )
    parser.add_argument("start", help="Начало диапазона дат, ДД.ММ.ГГГГ")
    parser.add_argument("end", help="Конец диапазона дат, ДД.ММ.ГГГГ")
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Показать окно браузера и не закрывать его автоматически",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(run(f"{args.start}-{args.end}", headful=args.headful))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
