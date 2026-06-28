"""Загрузка и валидация конфигурации приложения из файла `.env`.

Все настройки централизованы в классе :class:`Settings`, который читает
переменные окружения с помощью pydantic-settings. Это даёт типизацию,
значения по умолчанию и понятные ошибки при некорректной конфигурации.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из переменных окружения / `.env`.

    Attributes:
        bot_token: Токен Telegram-бота от @BotFather.
        database_url: Строка подключения к PostgreSQL (драйвер asyncpg).
        vfs_base_url: Базовый URL сайта VFS Global.
        vfs_login: Логин личного кабинета VFS (опционально).
        vfs_password: Пароль личного кабинета VFS (опционально).
        check_interval_seconds: Интервал опроса слотов планировщиком, сек.
        browser_headless: Запускать ли браузер без графического интерфейса.
        browser_timeout_ms: Таймаут ожидания элементов страницы, мс.
        captcha_api_key: Ключ внешнего сервиса решения капчи (опционально).
        session_storage_path: Каталог для хранения сохранённых сессий браузера.
        session_max_age_hours: Максимальный возраст сессии в часах.
        log_level: Уровень логирования loguru.
        log_file: Путь к файлу логов.
    """

    # --- Telegram ---
    # Опционально: бот может не запускаться (например, при автономной
    # проверке слотов через run_check.py). Проверка наличия — в main.py.
    bot_token: str | None = Field(default=None, description="Токен Telegram-бота")

    # --- База данных ---
    database_url: str = Field(
        default="postgresql+asyncpg://vfs_user:vfs_password@localhost:5432/vfs_bot",
        description="Строка подключения к PostgreSQL",
    )

    # --- VFS Global ---
    vfs_base_url: str = Field(default="https://visa.vfsglobal.com")
    vfs_login: str | None = Field(default=None)
    vfs_password: str | None = Field(default=None)

    # Критерии записи — что выбирать в выпадающих списках шага 1.
    # Текст как на сайте (допускается частичное совпадение). Это параметры
    # «задачи»: сейчас из .env, в будущем — из Telegram/веб-интерфейса.
    vfs_center: str | None = Field(default=None)
    vfs_category: str | None = Field(default=None)
    vfs_subcategory: str | None = Field(default=None)

    # --- Планировщик ---
    check_interval_seconds: int = Field(default=300, ge=30)

    # --- Браузер ---
    browser_headless: bool = Field(default=True)
    browser_timeout_ms: int = Field(default=30_000, ge=1_000)
    # Сколько браузеров держать в пуле воркера (параллельная обработка задач).
    worker_browsers: int = Field(default=1, ge=1)

    # --- Прокси (опционально, для обхода IP-блокировок VFS, напр. 403201) ---
    # Формат сервера: "http://host:port" или "socks5://host:port".
    proxy_server: str | None = Field(default=None)
    proxy_username: str | None = Field(default=None)
    proxy_password: str | None = Field(default=None)

    # --- Капча ---
    captcha_api_key: str | None = Field(default=None)

    # --- Сессии браузера ---
    session_storage_path: str = Field(default="sessions")
    session_max_age_hours: int = Field(default=24, ge=1)

    # --- Логирование ---
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="logs/bot.log")

    model_config = SettingsConfigDict(
        # .env лежит в корне проекта; сервисы запускаются из backend/, поэтому
        # ищем и в корне (../.env), и рядом (.env).
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Вернуть singleton-экземпляр настроек.

    Используется кэширование, чтобы `.env` читался только один раз
    за время жизни процесса.

    Returns:
        Settings: Загруженные и провалидированные настройки.
    """
    return Settings()  # type: ignore[call-arg]
