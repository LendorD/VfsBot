"""Юнит-тесты менеджера персистентных сессий.

Тесты не запускают реальный браузер: ``BrowserContext`` подменяется лёгким
фейком с асинхронным методом ``storage_state()``. Проверяются сохранение,
загрузка, оценка валидности (возраст и срок действия cookies) и удаление.
"""

from __future__ import annotations

import json
import time

import pytest

from vfs_site.session import SessionManager


class FakeContext:
    """Минимальная замена ``BrowserContext`` для тестов сохранения."""

    def __init__(self, state: dict) -> None:
        self._state = state

    async def storage_state(self, **_kwargs: object) -> dict:
        """Вернуть заранее заданное состояние сессии."""
        return self._state


def _state_with_cookie(expires: float) -> dict:
    """Сформировать ``storage_state`` с одной cookie заданного срока."""
    return {
        "cookies": [
            {
                "name": "session",
                "value": "abc",
                "domain": ".vfsglobal.com",
                "path": "/",
                "expires": expires,
            }
        ],
        "origins": [],
    }


@pytest.mark.asyncio
async def test_save_and_load_session(tmp_path) -> None:
    """Сохранённая сессия успешно загружается обратно."""
    manager = SessionManager(storage_path=str(tmp_path), max_age_hours=24)
    context = FakeContext(_state_with_cookie(time.time() + 3600))

    await manager.save_session(context, user_id=1)
    loaded = await manager.load_session(1)

    assert loaded is not None
    assert loaded["cookies"][0]["name"] == "session"


@pytest.mark.asyncio
async def test_missing_session_returns_none(tmp_path) -> None:
    """Отсутствие файла сессии возвращает None."""
    manager = SessionManager(storage_path=str(tmp_path), max_age_hours=24)
    assert await manager.load_session(999) is None


@pytest.mark.asyncio
async def test_session_expired_by_age(tmp_path) -> None:
    """Сессия старше max_age_hours считается невалидной."""
    manager = SessionManager(storage_path=str(tmp_path), max_age_hours=1)
    path = tmp_path / "5.json"
    payload = {
        "saved_at": time.time() - 7200,  # 2 часа назад
        "state": _state_with_cookie(time.time() + 3600),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert await manager.load_session(5) is None


@pytest.mark.asyncio
async def test_session_expired_cookies(tmp_path) -> None:
    """Сессия с истёкшими cookies считается невалидной."""
    manager = SessionManager(storage_path=str(tmp_path), max_age_hours=24)
    path = tmp_path / "6.json"
    payload = {
        "saved_at": time.time(),
        "state": _state_with_cookie(time.time() - 10),  # уже истекла
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert await manager.load_session(6) is None


@pytest.mark.asyncio
async def test_corrupted_session_returns_none(tmp_path) -> None:
    """Повреждённый JSON не приводит к падению — возвращается None."""
    manager = SessionManager(storage_path=str(tmp_path), max_age_hours=24)
    (tmp_path / "7.json").write_text("{ not json", encoding="utf-8")

    assert await manager.load_session(7) is None


@pytest.mark.asyncio
async def test_clear_session(tmp_path) -> None:
    """Удаление сессии делает её недоступной для загрузки."""
    manager = SessionManager(storage_path=str(tmp_path), max_age_hours=24)
    context = FakeContext(_state_with_cookie(time.time() + 3600))
    await manager.save_session(context, user_id=8)

    manager.clear_session(8)

    assert await manager.load_session(8) is None


def test_is_session_valid_without_cookies(tmp_path) -> None:
    """Состояние без cookies всегда невалидно."""
    manager = SessionManager(storage_path=str(tmp_path), max_age_hours=24)
    payload = {"saved_at": time.time(), "state": {"cookies": [], "origins": []}}

    assert manager.is_session_valid(payload) is False
