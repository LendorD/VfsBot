"""Интерфейс решения капчи (заглушка).

Модуль определяет абстрактный контракт :class:`CaptchaSolver` и его
заглушечную реализацию :class:`StubCaptchaSolver`. Реальная интеграция
(например, с внешним сервисом распознавания) должна реализовать тот же
интерфейс и подставляться через настройку ``CAPTCHA_API_KEY``.

ВАЖНО: автоматическое решение капчи может нарушать условия использования
сайта VFS Global. Используйте этот модуль только в рамках, допустимых
правилами сервиса и применимым законодательством.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from loguru import logger

from utils.exceptions import CaptchaError


class CaptchaSolver(ABC):
    """Абстрактный решатель капчи.

    Конкретные реализации получают данные капчи (изображение, ключ сайта
    reCAPTCHA и т.п.) и возвращают код/токен для подстановки в форму.
    """

    @abstractmethod
    async def solve_image_captcha(self, image_bytes: bytes) -> str:
        """Решить графическую (текстовую) капчу.

        Args:
            image_bytes: Изображение капчи в виде байтов.

        Returns:
            str: Распознанный текст капчи.

        Raises:
            CaptchaError: Если решить капчу не удалось.
        """
        raise NotImplementedError

    @abstractmethod
    async def solve_recaptcha(self, site_key: str, page_url: str) -> str:
        """Решить reCAPTCHA и вернуть токен.

        Args:
            site_key: Публичный ключ сайта (data-sitekey).
            page_url: URL страницы с капчей.

        Returns:
            str: Токен g-recaptcha-response.

        Raises:
            CaptchaError: Если решить капчу не удалось.
        """
        raise NotImplementedError


class StubCaptchaSolver(CaptchaSolver):
    """Заглушечная реализация: не решает капчу, а сообщает о необходимости.

    Возвращает управление вызывающему коду с явной ошибкой, чтобы заявка
    перешла в статус ``error`` и пользователь был уведомлён. Замените на
    реальную реализацию при необходимости.
    """

    async def solve_image_captcha(self, image_bytes: bytes) -> str:  # noqa: D102
        logger.warning(
            "Вызван StubCaptchaSolver.solve_image_captcha — капча не решена "
            "(размер изображения: {} байт)",
            len(image_bytes),
        )
        raise CaptchaError(
            "Решение графической капчи не реализовано. "
            "Подключите внешний сервис в captcha_solver.py."
        )

    async def solve_recaptcha(self, site_key: str, page_url: str) -> str:  # noqa: D102
        logger.warning(
            "Вызван StubCaptchaSolver.solve_recaptcha — капча не решена "
            "(site_key={}, url={})",
            site_key,
            page_url,
        )
        raise CaptchaError(
            "Решение reCAPTCHA не реализовано. "
            "Подключите внешний сервис в captcha_solver.py."
        )


def get_captcha_solver(api_key: str | None = None) -> CaptchaSolver:
    """Фабрика решателя капчи.

    На текущий момент всегда возвращает заглушку. При появлении реальной
    интеграции здесь следует выбирать реализацию в зависимости от наличия
    ``api_key``.

    Args:
        api_key: Ключ внешнего сервиса (если задан).

    Returns:
        CaptchaSolver: Экземпляр решателя капчи.
    """
    if api_key:
        logger.info("CAPTCHA_API_KEY задан, но реальный решатель не подключён")
    return StubCaptchaSolver()
