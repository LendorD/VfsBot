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
        log_level: Уровень логирования loguru.
        log_file: Путь к файлу логов.
    """

    # --- Telegram ---
    bot_token: str = Field(..., description="Токен Telegram-бота")

    # --- База данных ---
    database_url: str = Field(
        default="postgresql+asyncpg://vfs_user:vfs_password@localhost:5432/vfs_bot",
        description="Строка подключения к PostgreSQL",
    )

    # --- VFS Global ---
    vfs_base_url: str = Field(default="https://visa.vfsglobal.com")
    vfs_login: str | None = Field(default=None)
    vfs_password: str | None = Field(default=None)

    # --- Планировщик ---
    check_interval_seconds: int = Field(default=300, ge=30)

    # --- Браузер ---
    browser_headless: bool = Field(default=True)
    browser_timeout_ms: int = Field(default=30_000, ge=1_000)

    # --- Капча ---
    captcha_api_key: str | None = Field(default=None)

    # --- Логирование ---
    log_level: str = Field(default="INFO")
    log_file: str = Field(default="logs/bot.log")

    model_config = SettingsConfigDict(
        env_file=".env",
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
