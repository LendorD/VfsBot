"""Клиент VFS Global: проверка свободных слотов и запись с обработкой капчи.

ВНИМАНИЕ: это документированный КАРКАС со стабами. Реальная логика
взаимодействия с сайтом VFS Global не реализована, поскольку:
    * актуальная вёрстка и селекторы закрыты и периодически меняются;
    * сайт защищён анти-бот системами (WAF, поведенческий анализ, капча);
    * порядок шагов зависит от страны подачи и типа визы.

Методы помечены ``TODO`` в местах, где требуется реальная реализация под
конкретный визовый центр. Перед использованием обязательно ознакомьтесь с
Условиями использования VFS Global и применимым законодательством.

Структура клиента отражает типичный пользовательский сценарий:
    1. авторизация (login);
    2. выбор центра/категории визы;
    3. поиск свободного дня и времени в заданном диапазоне дат;
    4. заполнение формы заявителя;
    5. подтверждение брони и получение номера бронирования.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import date
from typing import Optional, Dict, Any

from loguru import logger
from playwright.async_api import BrowserContext, Page

from vfs_site import selectors
from captcha.solver import CaptchaSolver, CaptchaType
from vfs_site.browser import BrowserManager
from core.config import get_settings
from core.exceptions import (
    BookingError,
    SlotNotFoundError,
    VFSClientError,
    CaptchaError,
)


@dataclass(frozen=True)
class AvailableSlot:
    """Описание найденного свободного слота.

    Attributes:
        slot_date: Дата слота.
        slot_time: Время слота в формате «ЧЧ:ММ».
    """

    slot_date: date
    slot_time: str


@dataclass(frozen=True)
class BookingResult:
    """Результат успешного бронирования.

    Attributes:
        slot_date: Дата записи.
        slot_time: Время записи.
        reference: Номер бронирования.
    """

    slot_date: date
    slot_time: str
    reference: str


class VFSClient:
    """Клиент для проверки и бронирования слотов на сайте VFS Global.

    Args:
        manager: Менеджер браузера для создания контекстов.
        captcha_solver: Решатель капчи (по умолчанию — заглушка).
    """

    def __init__(
        self, manager: BrowserManager, captcha_solver: CaptchaSolver
    ) -> None:
        self._manager = manager
        self._captcha_solver = captcha_solver
        self._settings = get_settings()
        self._page: Optional[Page] = None

    # ================================================================== #
    # Публичный API
    # ================================================================== #
    async def find_slot(
        self, start_date: date, end_date: date
    ) -> AvailableSlot | None:
        """Найти первый свободный слот в диапазоне дат.

        Открывает новый контекст браузера, авторизуется, переходит к
        календарю и ищет доступный день/время в пределах [start_date; end_date].

        Args:
            start_date: Начало диапазона поиска.
            end_date: Конец диапазона поиска.

        Returns:
            AvailableSlot, если слот найден, иначе None.

        Raises:
            VFSClientError: При ошибке взаимодействия с сайтом.
        """
        logger.info("Поиск слота в диапазоне {} — {}", start_date, end_date)
        context = await self._manager.new_context()
        try:
            page = await context.new_page()
            await self._open_booking_page(page)
            slot = await self._scan_calendar(page, start_date, end_date)
            if slot is None:
                logger.info("Свободные слоты в диапазоне не найдены")
            else:
                logger.info(
                    "Найден слот: {} {}", slot.slot_date, slot.slot_time
                )
            return slot
        finally:
            await context.close()

    async def book_slot(
        self, applicant: dict, start_date: date, end_date: date
    ) -> BookingResult:
        """Найти слот и выполнить полное бронирование для заявителя.

        Args:
            applicant: Словарь персональных данных заявителя (фамилия, имя,
                паспорт, email, телефон и даты).
            start_date: Начало диапазона поиска.
            end_date: Конец диапазона поиска.

        Returns:
            BookingResult: Реквизиты успешной брони.

        Raises:
            SlotNotFoundError: Если свободных слотов нет.
            BookingError: Если бронирование не удалось завершить.
            VFSClientError: При иной ошибке взаимодействия с сайтом.
        """
        logger.info("Старт бронирования для {} {}",
                    applicant.get("surname"), applicant.get("name"))
        context = await self._manager.new_context()
        try:
            page = await context.new_page()
            await self._open_booking_page(page)

            slot = await self._scan_calendar(page, start_date, end_date)
            if slot is None:
                raise SlotNotFoundError(
                    "Свободных слотов в заданном диапазоне нет"
                )

            await self._select_slot(page, slot)
            await self._fill_applicant_form(page, applicant)
            result = await self._confirm_booking(page, slot)
            logger.info("Бронирование успешно: №{}", result.reference)
            return result
        except VFSClientError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ошибка бронирования: {}", exc)
            raise BookingError("Не удалось завершить бронирование") from exc
        finally:
            await context.close()

    # ================================================================== #
    # Обработка капчи (универсальная)
    # ================================================================== #
    async def _handle_captcha_anywhere(self, page: Page, context: str = "") -> bool:
        """Универсальная проверка и решение капчи в любом месте.

        Args:
            page: Страница для проверки
            context: Контекст вызова для логирования

        Returns:
            bool: True если капча успешно пройдена или отсутствует
        """
        try:
            # 1. Определяем тип капчи
            captcha_type = await self._captcha_solver.detect_captcha_type(page)
            
            if captcha_type == CaptchaType.UNKNOWN:
                logger.debug(f"Капча не обнаружена ({context})")
                return True

            logger.warning(f"🔍 Обнаружена капча {captcha_type.value} ({context})")

            # 2. Пробуем через Playwright (эмуляция человека)
            result = await self._captcha_solver.solve_captcha_with_playwright(page)
            
            if result.success:
                logger.info(f"✅ Капча пройдена через Playwright ({context})")
                return True

            # 3. Если не сработало — пробуем через curl_cffi
            logger.warning(f"⚠️ Playwright не помог, пробуем curl_cffi ({context})")
            content = await self._captcha_solver.solve_with_curl(page.url)
            
            if content:
                logger.info(f"✅ Капча пройдена через curl_cffi ({context})")
                # Перезагружаем страницу с новым контентом
                await page.reload()
                await asyncio.sleep(random.uniform(1, 2))
                return True

            logger.error(f"❌ Не удалось пройти капчу ({context})")
            return False

        except Exception as e:
            logger.error(f"Ошибка обработки капчи ({context}): {e}")
            return False

    async def _check_captcha_after_action(self, page: Page, action: str = "") -> bool:
        """Проверить капчу после действия (клик, сабмит).

        Args:
            page: Страница для проверки
            action: Название действия для логирования

        Returns:
            bool: True если капча успешно пройдена
        """
        # Небольшая пауза для появления капчи
        await asyncio.sleep(random.uniform(1.5, 3))
        
        # Проверяем наличие капчи
        captcha_detected = await self._captcha_solver.detect_captcha_type(page)
        
        if captcha_detected != CaptchaType.UNKNOWN:
            logger.warning(f"🔍 Обнаружена капча после действия: {action}")
            return await self._handle_captcha_anywhere(page, f"after_{action}")
        
        return True

    # ================================================================== #
    # Внутренние шаги (реализация с капчей)
    # ================================================================== #
    async def _open_booking_page(self, page: Page) -> None:
        """Открыть страницу бронирования с обработкой капчи."""
        logger.debug("Открытие страницы записи: {}", self._settings.vfs_base_url)
        
        # 1. Загружаем страницу
        await page.goto(self._settings.vfs_base_url, wait_until="domcontentloaded")
        await asyncio.sleep(random.uniform(1, 3))
        
        # 2. ⭐ ПРОВЕРКА КАПЧИ — Cloudflare может появиться сразу
        if not await self._handle_captcha_anywhere(page, "open_booking"):
            raise VFSClientError("Не удалось открыть страницу из-за Cloudflare")
        
        # 3. Проверяем, что мы на правильной странице
        if "captcha" in page.url.lower() or "challenge" in page.url.lower():
            raise VFSClientError("Страница заблокирована Cloudflare")
        
        # 4. Выбираем страну/центр (если нужно)
        await self._select_country_center(page)
        
        logger.info("✅ Страница бронирования успешно открыта")

    async def _select_country_center(self, page: Page) -> None:
        """Выбрать страну и визовый центр с обработкой капчи."""
        logger.debug("Выбор страны и центра")
        
        # TODO: реализовать выбор страны/центра
        # 1. Найти dropdown страны
        # 2. Выбрать нужную страну из self._settings.vfs_country
        # 3. Найти dropdown центра
        # 4. Выбрать нужный центр из self._settings.vfs_center
        
        # ⭐ Проверка капчи после выбора
        await self._check_captcha_after_action(page, "select_country")
        
        logger.info("✅ Страна и центр выбраны")

    async def _login_if_needed(self, page: Page) -> bool:
        """Выполнить вход в личный кабинет если требуется."""
        # Проверяем, нужно ли логиниться
        if "login" not in page.url.lower() and "signin" not in page.url.lower():
            return True

        logger.info("Выполнение входа в личный кабинет")
        
        try:
            # 1. ⭐ ПРОВЕРКА КАПЧИ на странице логина
            if not await self._handle_captcha_anywhere(page, "login_page"):
                raise VFSClientError("Не удалось загрузить страницу логина из-за Cloudflare")
            
            # 2. Вводим логин
            username_field = page.locator('input[name="username"], #username, input[type="email"]')
            await username_field.wait_for(state="visible", timeout=10000)
            await username_field.fill(self._settings.vfs_username)
            
            # 3. Вводим пароль
            password_field = page.locator('input[name="password"], #password')
            await password_field.wait_for(state="visible", timeout=10000)
            await password_field.fill(self._settings.vfs_password)
            
            # 4. ⭐ КАПЧА ПОД ПАРОЛЕМ — часто появляется после ввода данных
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Проверяем наличие Turnstile под полем пароля
            turnstile_detected = await self._captcha_solver._find_turnstile_iframe(page)
            if turnstile_detected:
                logger.info("🔍 Обнаружен Cloudflare Turnstile под полем пароля")
                result = await self._captcha_solver.solve_turnstile_with_playwright(page)
                if not result.success:
                    raise CaptchaError("Не удалось пройти Turnstile на форме логина")
            
            # 5. Нажимаем кнопку входа
            submit_btn = page.locator('button[type="submit"], .login-button, [name="login"]')
            await submit_btn.click()
            
            # 6. ⭐ ПРОВЕРКА КАПЧИ ПОСЛЕ САБМИТА
            if not await self._check_captcha_after_action(page, "login_submit"):
                raise CaptchaError("Капча после логина не пройдена")
            
            # 7. Ждём загрузки после входа
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(random.uniform(1, 2))
            
            # 8. Проверяем, что зашли
            if "/dashboard" in page.url or "/account" in page.url or "/my" in page.url:
                logger.info("✅ Успешный вход в личный кабинет")
                return True
            
            logger.warning("❌ Не удалось войти, возможно требуется дополнительная проверка")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при входе: {e}")
            return False

    async def _scan_calendar(
        self, page: Page, start_date: date, end_date: date
    ) -> AvailableSlot | None:
        """Просканировать календарь и вернуть первый свободный слот в диапазоне.

        TODO: реализовать обход календаря:
            * прочитать доступные дни (selectors.BOOKING.available_day);
            * отфильтровать по диапазону [start_date; end_date];
            * для первого подходящего дня выбрать доступное время
              (selectors.BOOKING.time_slot).

        Args:
            page: Открытая страница с календарём.
            start_date: Начало диапазона.
            end_date: Конец диапазона.

        Returns:
            AvailableSlot или None.
        """
        logger.debug("Сканирование календаря {}..{}", start_date, end_date)
        
        # ⭐ Проверка капчи перед сканированием
        if not await self._check_captcha_after_action(page, "before_scan"):
            raise VFSClientError("Капча перед сканированием календаря не пройдена")
        
        _ = selectors.BOOKING  # селекторы для будущей реализации
        # TODO: реальный обход календаря и фильтрация по датам.
        
        # Имитация поиска (заглушка)
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # ⭐ Проверка капчи после сканирования
        await self._check_captcha_after_action(page, "scan_calendar")
        
        return None

    async def _select_slot(self, page: Page, slot: AvailableSlot) -> None:
        """Выбрать конкретный день и время в календаре.

        TODO: кликнуть по дню ``slot.slot_date`` и времени ``slot.slot_time``.

        Args:
            page: Открытая страница.
            slot: Найденный слот для выбора.
        """
        logger.debug("Выбор слота {} {}", slot.slot_date, slot.slot_time)
        
        # ⭐ Проверка капчи перед выбором слота
        if not await self._check_captcha_after_action(page, "before_select_slot"):
            raise VFSClientError("Капча перед выбором слота не пройдена")
        
        # TODO: реальные клики по элементам календаря.
        # 1. Клик по дню: page.locator(selectors.BOOKING.day.format(date=slot.slot_date))
        # 2. Клик по времени: page.locator(selectors.BOOKING.time.format(time=slot.slot_time))
        
        # Имитация выбора
        await asyncio.sleep(random.uniform(0.5, 1))
        
        # ⭐ Проверка капчи после выбора слота
        await self._check_captcha_after_action(page, "select_slot")

    async def _fill_applicant_form(self, page: Page, applicant: dict) -> None:
        """Заполнить форму персональных данных заявителя.

        TODO: заполнить поля формы (selectors.APPLICANT_FORM) значениями из
        ``applicant`` и отправить форму.

        Args:
            page: Открытая страница с формой.
            applicant: Персональные данные заявителя.
        """
        logger.debug("Заполнение формы заявителя")
        
        # ⭐ Проверка капчи перед заполнением
        if not await self._check_captcha_after_action(page, "before_fill_form"):
            raise VFSClientError("Капча перед заполнением формы не пройдена")
        
        _ = selectors.APPLICANT_FORM
        
        # TODO: реальное заполнение полей формы.
        # Пример:
        # await page.fill(selectors.APPLICANT_FORM.surname, applicant["surname"])
        # await page.fill(selectors.APPLICANT_FORM.name, applicant["name"])
        # и т.д.
        
        # Имитация заполнения
        await asyncio.sleep(random.uniform(1, 2))
        
        # ⭐ Проверка капчи после заполнения
        await self._check_captcha_after_action(page, "fill_form")

    async def _confirm_booking(
        self, page: Page, slot: AvailableSlot
    ) -> BookingResult:
        """Подтвердить бронирование и считать номер брони.

        TODO: нажать кнопку подтверждения, дождаться страницы успеха и
        прочитать номер бронирования (selectors.CONFIRMATION).

        Args:
            page: Открытая страница подтверждения.
            slot: Забронированный слот.

        Returns:
            BookingResult: Реквизиты брони.

        Raises:
            BookingError: Заглушка всегда сообщает о нереализованной логике.
        """
        logger.debug("Подтверждение бронирования")
        
        # ⭐ Проверка капчи перед подтверждением
        if not await self._check_captcha_after_action(page, "before_confirm"):
            raise VFSClientError("Капча перед подтверждением не пройдена")
        
        _ = selectors.CONFIRMATION
        
        # TODO: реальное подтверждение и чтение номера брони.
        # 1. Нажать кнопку подтверждения
        # 2. Дождаться страницы успеха
        # 3. Прочитать номер бронирования
        
        # Имитация подтверждения
        await asyncio.sleep(random.uniform(1, 2))
        
        # ⭐ Проверка капчи после подтверждения
        await self._check_captcha_after_action(page, "confirm_booking")
        
        raise BookingError(
            "Подтверждение брони VFS не реализовано (каркас)."
        )

    # ================================================================== #
    # Вспомогательные методы
    # ================================================================== #
    async def _ensure_page(self) -> Page:
        """Получить или создать страницу."""
        if not self._page:
            self._page = await self._manager.new_page()
        return self._page