"""Управление браузером и контекстами Playwright.

Класс :class:`BrowserManager` инкапсулирует жизненный цикл браузера:
запуск/остановку и создание контекстов с восстановлением cookies/localStorage.

Поддерживаются два режима запуска:

* обычный (``persistent=False``) — встроенный Chromium, отдельный контекст
  на заявку. Используется ботом и ``run_check.py``;
* персистентный (``persistent=True``) — реальный Chrome с постоянным
  профилем (``user_data_dir``). Профиль сохраняет cookie ``cf_clearance``
  между запусками, поэтому проверку Cloudflare достаточно пройти один раз.
  Используется ``inspect_page.py`` для обхода анти-бот защиты.

Если установлен пакет ``patchright`` (патченый Playwright, маскирующий
CDP-утечку, по которой Cloudflare детектит автоматизацию), движок запуска
берётся из него. Иначе используется обычный ``playwright``.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

# Типы берём из playwright (он установлен всегда). Движок запуска — patchright,
# если доступен; иначе обычный playwright.
from playwright.async_api import Browser, BrowserContext, Playwright

try:  # pragma: no cover - зависит от окружения
    from patchright.async_api import async_playwright

    _ENGINE = "patchright"
except ImportError:  # patchright не установлен
    from playwright.async_api import async_playwright

    _ENGINE = "playwright"

from vfs_site.session import SessionManager
from core.config import get_settings
from core.exceptions import BrowserError

# User-Agent обычного десктопного браузера, чтобы снизить вероятность
# тривиальной детекции автоматизации.
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Небольшой стелс-скрипт: убирает самый явный признак автоматизации.
# Полноценный обход CDP-детекта обеспечивает patchright, не этот скрипт.
_STEALTH_JS = "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"


class BrowserManager:
    """Менеджер жизненного цикла браузера и контекстов."""

    def __init__(self, session_manager: SessionManager | None = None) -> None:
        """Инициализировать менеджер без запуска браузера.

        Args:
            session_manager: Менеджер персистентных сессий. Если не передан,
                создаётся менеджер с настройками по умолчанию.
        """
        self._settings = get_settings()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        # Персистентный контекст (если запуск был с persistent=True).
        self._persistent_context: BrowserContext | None = None
        self._session_manager = session_manager or SessionManager()

    def _proxy_config(self) -> dict[str, str] | None:
        """Сформировать конфиг прокси из настроек (или None, если не задан)."""
        if not self._settings.proxy_server:
            return None
        proxy: dict[str, str] = {"server": self._settings.proxy_server}
        if self._settings.proxy_username:
            proxy["username"] = self._settings.proxy_username
        if self._settings.proxy_password:
            proxy["password"] = self._settings.proxy_password
        logger.info("Используется прокси: {}", self._settings.proxy_server)
        return proxy

    async def start(
        self,
        headless: bool | None = None,
        persistent: bool = False,
        user_data_dir: str | None = None,
        channel: str | None = "chrome",
    ) -> None:
        """Запустить браузер.

        Args:
            headless: Переопределить режим из настроек. ``None`` — взять
                ``BROWSER_HEADLESS`` из ``.env``; ``False`` — показать окно.
            persistent: Запустить реальный Chrome с постоянным профилем
                (нужно для сохранения cookie Cloudflare между запусками).
            user_data_dir: Каталог профиля для персистентного режима.
            channel: Канал браузера для персистентного режима (``"chrome"`` —
                реальный Chrome; ``None`` — встроенный Chromium).

        Raises:
            BrowserError: Если запустить браузер не удалось.
        """
        effective_headless = (
            self._settings.browser_headless if headless is None else headless
        )
        logger.info("Движок браузера: {}", _ENGINE)
        try:
            self._playwright = await async_playwright().start()
            if persistent:
                await self._start_persistent(
                    effective_headless, user_data_dir or ".browser_profile", channel
                )
            else:
                self._browser = await self._playwright.chromium.launch(
                    headless=effective_headless,
                    proxy=self._proxy_config(),
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                )
            logger.info(
                "Браузер запущен (headless={}, persistent={})",
                effective_headless,
                persistent,
            )
        except Exception as exc:  # noqa: BLE001 - оборачиваем в доменную ошибку
            logger.exception("Не удалось запустить браузер: {}", exc)
            raise BrowserError("Не удалось запустить браузер") from exc

    async def _start_persistent(
        self, headless: bool, user_data_dir: str, channel: str | None
    ) -> None:
        """Запустить персистентный контекст (реальный Chrome + профиль).

        При отсутствии реального Chrome откатывается на встроенный Chromium.
        """

        # ВАЖНО: «чистый» запуск без ручных стелс-костылей. patchright сам
        # корректно маскирует автоматизацию; лишние args, подмена User-Agent
        # и init-скрипты, наоборот, выдают бота Cloudflare. Поэтому здесь
        # НЕ передаём args, user_agent и не добавляем add_init_script.
        async def _launch(use_channel: str | None) -> BrowserContext:
            return await self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless,
                channel=use_channel,
                no_viewport=True,
                proxy=self._proxy_config(),
            )

        try:
            self._persistent_context = await _launch(channel)
        except Exception as exc:  # noqa: BLE001 - реальный Chrome не найден
            logger.warning(
                "Канал '{}' недоступен ({}). Использую встроенный Chromium.",
                channel,
                exc,
            )
            self._persistent_context = await _launch(None)

        self._persistent_context.set_default_timeout(
            self._settings.browser_timeout_ms
        )
        self._browser = self._persistent_context.browser

    @property
    def is_connected(self) -> bool:
        """True, пока окно браузера открыто и не закрыто пользователем."""
        return self._browser is not None and self._browser.is_connected()

    async def stop(self) -> None:
        """Корректно остановить браузер и Playwright.

        Безопасно вызывать повторно и даже если пользователь уже закрыл
        окно браузера вручную (ошибки закрытия подавляются).
        """
        if self._persistent_context is not None:
            try:
                await self._persistent_context.close()
            except Exception:  # noqa: BLE001 - окно могло быть уже закрыто
                pass
            self._persistent_context = None
            self._browser = None
        elif self._browser is not None:
            try:
                await self._browser.close()
            except Exception:  # noqa: BLE001 - браузер мог быть уже закрыт
                pass
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Браузер остановлен")

    async def new_context(
        self, storage_state: dict[str, Any] | None = None
    ) -> BrowserContext:
        """Создать (или вернуть) контекст браузера.

        В персистентном режиме возвращается единый профильный контекст.
        В обычном режиме создаётся новый изолированный контекст.

        Args:
            storage_state: Сохранённое состояние сессии (только для обычного
                режима; в персистентном игнорируется — состояние хранит профиль).

        Returns:
            BrowserContext: Готовый к использованию контекст.

        Raises:
            BrowserError: Если браузер не запущен.
        """
        if self._persistent_context is not None:
            return self._persistent_context

        if self._browser is None:
            raise BrowserError("Браузер не запущен. Сначала вызовите start().")

        context = await self._browser.new_context(
            user_agent=_DEFAULT_USER_AGENT,
            locale="ru-RU",
            storage_state=storage_state,
        )
        await context.add_init_script(_STEALTH_JS)
        context.set_default_timeout(self._settings.browser_timeout_ms)
        logger.debug("Создан новый контекст браузера")
        return context

    async def new_context_for_user(self, user_id: int) -> BrowserContext:
        """Создать контекст, восстановив сохранённую сессию пользователя.

        Если для пользователя есть валидная сохранённая сессия, она будет
        подставлена в контекст. Иначе создаётся «чистый» контекст.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            BrowserContext: Контекст с восстановленной сессией (если была).
        """
        storage_state = await self._session_manager.load_session(user_id)
        return await self.new_context(storage_state=storage_state)

    async def save_session(self, context: BrowserContext, user_id: int) -> None:
        """Сохранить текущую сессию контекста для пользователя.

        Args:
            context: Контекст браузера с активной сессией.
            user_id: Идентификатор пользователя.
        """
        await self._session_manager.save_session(context, user_id)

    @property
    def session_manager(self) -> SessionManager:
        """Менеджер персистентных сессий, используемый этим браузером."""
        return self._session_manager

    async def __aenter__(self) -> "BrowserManager":
        """Поддержка асинхронного контекстного менеджера: запуск."""
        await self.start()
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Поддержка асинхронного контекстного менеджера: остановка."""
        await self.stop()
