"""Управление браузером и контекстами Playwright.

Класс :class:`BrowserManager` инкапсулирует жизненный цикл Playwright:
запуск/остановку браузера и создание изолированных контекстов с
восстановлением cookies/localStorage из сохранённой сессии.

Один браузер на процесс, отдельный контекст на заявку — это снижает
взаимное влияние параллельных проверок и упрощает работу с сессиями.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    Playwright,
    async_playwright,
)

from utils.config import get_settings
from utils.exceptions import BrowserError

# User-Agent обычного десктопного браузера, чтобы снизить вероятность
# тривиальной детекции автоматизации.
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class BrowserManager:
    """Менеджер жизненного цикла браузера и контекстов Playwright."""

    def __init__(self) -> None:
        """Инициализировать менеджер без запуска браузера."""
        self._settings = get_settings()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        """Запустить Playwright и браузер.

        Raises:
            BrowserError: Если запустить браузер не удалось.
        """
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._settings.browser_headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            logger.info(
                "Браузер запущен (headless={})", self._settings.browser_headless
            )
        except Exception as exc:  # noqa: BLE001 - оборачиваем в доменную ошибку
            logger.exception("Не удалось запустить браузер: {}", exc)
            raise BrowserError("Не удалось запустить браузер") from exc

    async def stop(self) -> None:
        """Корректно остановить браузер и Playwright."""
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Браузер остановлен")

    async def new_context(
        self, storage_state: dict[str, Any] | None = None
    ) -> BrowserContext:
        """Создать новый изолированный контекст браузера.

        Args:
            storage_state: Сохранённое состояние сессии Playwright
                (cookies + origins), если требуется восстановление.

        Returns:
            BrowserContext: Готовый к использованию контекст.

        Raises:
            BrowserError: Если браузер не запущен.
        """
        if self._browser is None:
            raise BrowserError("Браузер не запущен. Сначала вызовите start().")

        context = await self._browser.new_context(
            user_agent=_DEFAULT_USER_AGENT,
            locale="ru-RU",
            storage_state=storage_state,
        )
        context.set_default_timeout(self._settings.browser_timeout_ms)
        logger.debug("Создан новый контекст браузера")
        return context

    async def __aenter__(self) -> "BrowserManager":
        """Поддержка асинхронного контекстного менеджера: запуск."""
        await self.start()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Поддержка асинхронного контекстного менеджера: остановка."""
        await self.stop()
