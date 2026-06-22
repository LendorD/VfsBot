"""Общая конфигурация pytest.

Задаёт безопасные значения переменных окружения до загрузки настроек,
чтобы тесты не требовали реального файла ``.env``.
"""

from __future__ import annotations

import os

# Подставляем фиктивные значения обязательных настроек для тестовой среды.
os.environ.setdefault("BOT_TOKEN", "test:token")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test"
)
