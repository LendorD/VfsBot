"""Кастомные исключения приложения.

Иерархия исключений позволяет точечно обрабатывать ошибки бизнес-логики:
ошибки валидации данных пользователя, ошибки браузера/VFS, ошибки капчи и
ошибки доступа к БД.
"""

from __future__ import annotations


class VFSBotError(Exception):
    """Базовое исключение приложения. От него наследуются все остальные."""


# --- Валидация пользовательского ввода ---
class ValidationError(VFSBotError):
    """Введённые пользователем данные не прошли валидацию."""


class DateRangeError(ValidationError):
    """Некорректный диапазон дат (например, конец раньше начала)."""


# --- Браузер и VFS ---
class BrowserError(VFSBotError):
    """Ошибка управления браузером (запуск, переход, таймаут)."""


class VFSClientError(VFSBotError):
    """Ошибка взаимодействия с сайтом VFS Global."""


class SlotNotFoundError(VFSClientError):
    """Свободные слоты в заданном диапазоне не найдены."""


class BookingError(VFSClientError):
    """Не удалось завершить бронирование слота."""


class SessionExpiredError(VFSClientError):
    """Сессия VFS истекла, требуется повторная авторизация."""


# --- Капча ---
class CaptchaError(VFSBotError):
    """Не удалось решить капчу."""


# --- База данных ---
class DatabaseError(VFSBotError):
    """Ошибка доступа к базе данных."""


class ApplicationNotFoundError(DatabaseError):
    """Заявка с указанным идентификатором не найдена."""
