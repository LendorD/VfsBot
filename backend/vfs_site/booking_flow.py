"""Единый движок бронирования VFS.

:class:`BookingFlow` исполняет :class:`~core.booking_task.BookingTask` по шагам
на странице записи VFS. Движок не зависит от интерфейса: его одинаково вызывают
и Telegram-бот, и веб-бэкенд, и автономный скрипт.

Состояние реализации по шагам:
    1. select_criteria   — ГОТОВО (selectors.APP_DETAIL + material);
    2. check_availability — ГОТОВО (availability.read_availability);
    3. proceed_to_applicants — ЗАГЛУШКА (нужен селектор «Продолжить»);
    4. fill_applicants  — ЗАГЛУШКА (нужны селекторы формы + «Добавить заявителя»);
    5. confirm_summary  — ЗАГЛУШКА (нужен селектор «Продолжить» на сводке);
    6. pick_date        — ЗАГЛУШКА (нужны селекторы календаря);
    7. select_services  — ЗАГЛУШКА (нужны селекторы шага «Услуги»);
    8. pay              — ЗАГЛУШКА (нужны селекторы оплаты; под флагом auto_pay).

По мере присылки селекторов заглушки заменяются реальной логикой.
"""

from __future__ import annotations

from datetime import date

from loguru import logger
from playwright.async_api import Page

from vfs_site import availability, material, selectors
from core.booking_task import BookingTask, to_site_date
from core.config import get_settings
from core.exceptions import BookingError, SlotNotFoundError, VFSClientError


class BookingFlow:
    """Пошаговое исполнение задачи бронирования на странице VFS."""

    def __init__(self, page: Page) -> None:
        """Args:
        page: Открытая страница Playwright (уже на шаге 1 после входа).
        """
        self._page = page
        self._settings = get_settings()

    # ------------------------------------------------------------------ #
    # Вход и переход к шагу 1 (ГОТОВО — селекторы есть)
    # ------------------------------------------------------------------ #
    async def login_and_open(self, login: str, password: str) -> None:
        """Открыть логин, авторизоваться и дойти до шага 1 «Информация о подаче».

        Браузер видимый: при появлении полноэкранной проверки Cloudflare метод
        ЖДЁТ, пока пользователь пройдёт её вручную (до 5 минут), и продолжает.
        """
        page = self._page
        base = self._settings.vfs_base_url.rstrip("/")
        await page.goto(f"{base}/login", wait_until="domcontentloaded")
        await self._wait_for_cloudflare()      # пройди проверку руками в окне

        # Определяем, где мы: ЯВНО ждём появления формы входа (Angular-SPA
        # рендерит её не мгновенно). Если форма появилась — сессия новая,
        # логинимся. Если не появилась за 20 с — вероятно, уже авторизованы.
        need_login = False
        try:
            await page.wait_for_selector(selectors.LOGIN.email_input, timeout=20_000)
            need_login = True
        except Exception:  # noqa: BLE001
            need_login = False

        if need_login:
            logger.info("Сессия новая — выполняю вход")
            await page.fill(selectors.LOGIN.email_input, login)
            await page.fill(selectors.LOGIN.password_input, password)
            try:
                # «Войти» активна только после прохождения виджета Cloudflare.
                await page.click(selectors.LOGIN.submit_button, timeout=90_000)
            except Exception as exc:  # noqa: BLE001
                raise VFSClientError(
                    "Кнопка «Войти» не сработала (виджет Cloudflare на форме "
                    "или неверные данные входа)."
                ) from exc
            await page.wait_for_timeout(3000)
            await self._wait_for_cloudflare()
        else:
            logger.info("Форма входа не появилась — вероятно, уже авторизованы")

        # Перейти к записи: кнопка «Записаться на прием» в кабинете.
        try:
            await page.wait_for_selector(
                selectors.DASHBOARD.book_appointment_button,
                timeout=self._settings.browser_timeout_ms,
            )
            await page.click(selectors.DASHBOARD.book_appointment_button)
            await page.wait_for_timeout(2500)
            await self._wait_for_cloudflare()
        except Exception as exc:  # noqa: BLE001
            raise VFSClientError(
                "Не удалось дойти до шага записи (страница не та или Cloudflare)."
            ) from exc
        logger.info("Дошли до шага 1 «Информация о подаче документов»")

    async def _is_cloudflare(self) -> bool:
        """Показана ли ПОЛНОЭКРАННАЯ проверка Cloudflare (не виджет на форме)."""
        page = self._page
        try:
            title = (await page.title()).lower()
        except Exception:  # noqa: BLE001
            title = ""
        if "just a moment" in title:
            return True
        try:
            body = (await page.locator("body").inner_text(timeout=2000)).lower()
        except Exception:  # noqa: BLE001
            return False
        markers = (
            "выполнение проверки безопасности",
            "проверяет, что вы не бот",
            "checking your browser",
        )
        return any(m in body for m in markers)

    async def _wait_for_cloudflare(self, max_seconds: int = 300) -> None:
        """Дождаться, пока пользователь вручную пройдёт Cloudflare (видимый браузер)."""
        if not await self._is_cloudflare():
            return
        logger.warning(
            "Cloudflare: пройди проверку вручную в окне браузера (жду до {} с)...",
            max_seconds,
        )
        waited = 0
        while waited < max_seconds:
            await self._page.wait_for_timeout(1000)
            waited += 1
            if not await self._is_cloudflare():
                logger.info("Cloudflare пройден за ~{} с", waited)
                return
        logger.warning("Cloudflare: истёк таймаут ожидания")

    # ------------------------------------------------------------------ #
    # Шаг 1: критерии (ГОТОВО)
    # ------------------------------------------------------------------ #
    async def select_criteria(self, task: BookingTask) -> None:
        """Выбрать центр, категорию и подкатегорию (последовательно)."""
        page = self._page
        criteria = task.criteria

        chosen = await material.choose(
            page, selectors.APP_DETAIL.center_select, criteria.center
        )
        if chosen is None:
            raise VFSClientError(f"Центр не найден: {criteria.center}")
        await page.wait_for_timeout(1200)

        chosen = await material.choose(
            page, selectors.APP_DETAIL.category_select, criteria.category
        )
        if chosen is None:
            raise VFSClientError(f"Категория не найдена: {criteria.category}")
        await page.wait_for_timeout(1500)

        chosen = await material.choose(
            page, selectors.APP_DETAIL.subcategory_select, criteria.subcategory
        )
        if chosen is None:
            raise VFSClientError(f"Подкатегория не найдена: {criteria.subcategory}")
        await page.wait_for_timeout(1200)
        logger.info("Критерии выбраны: {} / {} / {}",
                    criteria.center, criteria.category, criteria.subcategory)

    # ------------------------------------------------------------------ #
    # Шаг 1: доступность (ГОТОВО)
    # ------------------------------------------------------------------ #
    async def find_available_date(self, task: BookingTask) -> date | None:
        """Вернуть подходящую дату из сообщения о доступности или None."""
        avail = await availability.read_availability(self._page)
        if not avail.recognized:
            logger.debug("Сообщение о доступности не распознано")
            return None
        slot = availability.matches_desired(
            avail,
            applicants=task.applicants_count,
            start=task.date_start,
            end=task.date_end,
        )
        if slot:
            logger.info("Подходящая дата найдена: {}", slot)
        return slot

    # ------------------------------------------------------------------ #
    # Шаг 1 → 2: переход к заявителям (ЗАГЛУШКА)
    # ------------------------------------------------------------------ #
    async def proceed_to_applicants(self) -> None:
        """Нажать «Продолжить» на шаге 1.

        TODO: добавить селектор кнопки «Продолжить» (шаг 1) в
        selectors.APP_DETAIL и реализовать клик.
        """
        raise BookingError(
            "proceed_to_applicants не реализован: нужен селектор кнопки "
            "«Продолжить» на шаге 1."
        )

    # ------------------------------------------------------------------ #
    # Шаг 2: данные заявителей (ЗАГЛУШКА)
    # ------------------------------------------------------------------ #
    async def fill_applicants(self, task: BookingTask) -> None:
        """Заполнить форму(ы) заявителей (любое число).

        Алгоритм (после получения селекторов):
            для каждого заявителя:
                заполнить Имя/Фамилия/Пол/Дату рождения/Гражданство/
                Паспорт/Срок/Телефон/Email (selectors.APPLICANT_FORM);
                если есть ещё — нажать «Добавить ещё одного заявителя».
        Даты переводятся в формат сайта через ``to_site_date``.

        TODO: заполнить selectors.APPLICANT_FORM реальными значениями и
        добавить селектор кнопки «Добавить ещё одного заявителя».
        """
        _ = (selectors.APPLICANT_FORM, to_site_date)  # пометка зависимостей
        raise BookingError(
            "fill_applicants не реализован: нужны селекторы полей формы "
            "заявителя и кнопки «Добавить ещё одного заявителя»."
        )

    async def confirm_summary(self) -> None:
        """Подтвердить сводку данных и перейти к календарю (ЗАГЛУШКА).

        TODO: селектор кнопки «Продолжить» на странице «Сводка ваших данных».
        """
        raise BookingError(
            "confirm_summary не реализован: нужен селектор «Продолжить» на сводке."
        )

    # ------------------------------------------------------------------ #
    # Шаг 3: календарь (ЗАГЛУШКА)
    # ------------------------------------------------------------------ #
    async def pick_date(self, task: BookingTask) -> date:
        """Выбрать доступную дату в календаре и время (ЗАГЛУШКА).

        Алгоритм (после получения селекторов):
            листать месяцы вперёд (кнопка «вперёд»);
            искать доступный (зелёный) день в диапазоне [date_start; date_end];
            кликнуть день, затем доступное время.

        TODO: заполнить selectors.BOOKING (контейнер календаря, доступный день,
        кнопка следующего месяца, слот времени).
        """
        raise BookingError(
            "pick_date не реализован: нужны селекторы календаря (день, "
            "переключение месяца, слот времени)."
        )

    # ------------------------------------------------------------------ #
    # Шаг 4: услуги (ЗАГЛУШКА)
    # ------------------------------------------------------------------ #
    async def select_services(self) -> None:
        """Пройти шаг «Услуги» (ЗАГЛУШКА).

        TODO: селекторы шага «Услуги» (выбор/пропуск доп. услуг и «Продолжить»).
        """
        raise BookingError(
            "select_services не реализован: нужны селекторы шага «Услуги»."
        )

    # ------------------------------------------------------------------ #
    # Шаг 5: оплата (ЗАГЛУШКА, под флагом auto_pay)
    # ------------------------------------------------------------------ #
    async def pay(self, task: BookingTask) -> None:
        """Шаг оплаты (ЗАГЛУШКА).

        Реальное списание выполняется ТОЛЬКО если ``task.auto_pay=True``.
        Иначе движок останавливается перед оплатой и оставляет всё готовым
        для ручного подтверждения.

        TODO: селекторы шага «Детали и оплата» и платёжной формы.
        """
        if not task.auto_pay:
            logger.warning("auto_pay=False — останавливаюсь перед оплатой")
            raise BookingError(
                "Дошли до оплаты. auto_pay выключен — подтвердите оплату вручную."
            )
        raise BookingError(
            "pay не реализован: нужны селекторы шага «Детали и оплата»."
        )

    # ------------------------------------------------------------------ #
    # Оркестрация
    # ------------------------------------------------------------------ #
    async def run(self, task: BookingTask) -> date:
        """Пройти весь сценарий: критерии → дата → форма → календарь → оплата.

        Returns:
            date: Забронированная дата.

        Raises:
            SlotNotFoundError: Если в диапазоне нет подходящей даты.
            BookingError: Если какой-то шаг не реализован/не удался.
        """
        await self.select_criteria(task)

        slot = await self.find_available_date(task)
        if slot is None:
            raise SlotNotFoundError("Подходящих слотов в диапазоне нет")

        await self.proceed_to_applicants()
        await self.fill_applicants(task)
        await self.confirm_summary()
        booked = await self.pick_date(task)
        await self.select_services()
        await self.pay(task)
        logger.info("Бронирование завершено на дату {}", booked)
        return booked
