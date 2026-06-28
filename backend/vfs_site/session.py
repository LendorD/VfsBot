"""Персистентное хранение состояния браузерной сессии.

Сохраняет и восстанавливает Playwright ``storage_state`` (cookies и данные
origins, включая localStorage), чтобы уже авторизованный пользователь не
проходил вход в личный кабинет при каждом запуске. Это стандартное
управление сессией («запомнить вход»), не связанное с обходом каких-либо
систем защиты.

Состояние хранится по одному JSON-файлу на пользователя в каталоге из
настройки ``SESSION_STORAGE_PATH``. Файл содержит время сохранения и сам
``storage_state``, что позволяет считать сессию устаревшей по возрасту.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from core.config import get_settings

if TYPE_CHECKING:  # Импорт только для аннотаций — не требуется в рантайме.
    from playwright.async_api import BrowserContext


class SessionManager:
    """Менеджер персистентных сессий браузера (Playwright ``storage_state``).

    Args:
        storage_path: Каталог для файлов сессий. По умолчанию берётся из
            настроек (``SESSION_STORAGE_PATH``).
        max_age_hours: Максимальный возраст сессии в часах, после которого
            она считается устаревшей. По умолчанию — из настроек
            (``SESSION_MAX_AGE_HOURS``).
    """

    def __init__(
        self,
        storage_path: str | None = None,
        max_age_hours: int | None = None,
    ) -> None:
        if storage_path is None or max_age_hours is None:
            settings = get_settings()
            storage_path = storage_path or settings.session_storage_path
            max_age_hours = (
                max_age_hours
                if max_age_hours is not None
                else settings.session_max_age_hours
            )

        self._dir = Path(storage_path)
        self._max_age_hours = max_age_hours
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, user_id: int) -> Path:
        """Вернуть путь к файлу сессии для пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Path: Путь к JSON-файлу сессии.
        """
        return self._dir / f"{user_id}.json"

    async def save_session(self, context: "BrowserContext", user_id: int) -> Path:
        """Сохранить состояние сессии контекста в файл пользователя.

        Использует штатный ``BrowserContext.storage_state()`` Playwright,
        который выгружает cookies и данные origins (localStorage).

        Args:
            context: Контекст браузера с активной сессией.
            user_id: Идентификатор пользователя.

        Returns:
            Path: Путь к сохранённому файлу сессии.
        """
        path = self._path_for(user_id)
        state = await context.storage_state()
        payload = {"saved_at": time.time(), "state": state}
        path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Сессия пользователя {} сохранена в {}", user_id, path)
        return path

    async def load_session(self, user_id: int) -> dict[str, Any] | None:
        """Загрузить ``storage_state`` пользователя, если он валиден.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Словарь ``storage_state`` для передачи в
            ``BrowserContext`` через ``storage_state=...``, либо ``None``,
            если сессии нет, она повреждена или устарела.
        """
        path = self._path_for(user_id)
        if not path.exists():
            logger.debug("Файл сессии для пользователя {} не найден", user_id)
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Не удалось прочитать сессию пользователя {}: {}", user_id, exc
            )
            return None

        if not isinstance(payload, dict) or not isinstance(
            payload.get("state"), dict
        ):
            logger.warning("Сессия пользователя {} повреждена", user_id)
            return None

        if not self.is_session_valid(payload):
            logger.info("Сессия пользователя {} устарела", user_id)
            return None

        logger.debug("Сессия пользователя {} загружена", user_id)
        return payload["state"]

    def is_session_valid(self, payload: dict[str, Any]) -> bool:
        """Проверить, не устарела ли сохранённая сессия.

        Сессия считается невалидной, если превышен максимальный возраст
        файла, если в состоянии нет cookies или если все cookies с указанным
        сроком действия уже истекли.

        Args:
            payload: Содержимое файла сессии (``saved_at`` + ``state``).

        Returns:
            bool: ``True``, если сессией можно пользоваться.
        """
        saved_at = float(payload.get("saved_at", 0) or 0)
        if self._max_age_hours and (
            time.time() - saved_at > self._max_age_hours * 3600
        ):
            return False

        state = payload.get("state", {})
        cookies = state.get("cookies", []) if isinstance(state, dict) else []
        if not cookies:
            return False

        now = time.time()
        # Учитываем только cookies с заданным положительным сроком действия.
        expiring = [
            c["expires"]
            for c in cookies
            if isinstance(c, dict) and c.get("expires", -1) and c.get("expires", -1) > 0
        ]
        if expiring and all(exp < now for exp in expiring):
            return False

        return True

    def clear_session(self, user_id: int) -> None:
        """Удалить сохранённый файл сессии пользователя.

        Используется, когда сессия признана нерабочей и должна быть
        пересоздана при следующем входе.

        Args:
            user_id: Идентификатор пользователя.
        """
        path = self._path_for(user_id)
        if path.exists():
            path.unlink()
            logger.info("Сессия пользователя {} удалена", user_id)
