"""Планировщик периодической проверки свободных слотов (APScheduler).

:class:`SlotChecker` с заданным интервалом обходит все активные заявки и
пытается найти/забронировать слот через :class:`VFSClient`. О результатах
пользователь уведомляется через переданный callback ``notifier``.

Чтобы один и тот же пользователь не обрабатывался дважды одновременно,
обработка каждой заявки защищена набором «в работе» (``_in_progress``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from vfs_site.client import VFSClient
from storage.database import Database
from storage.models import Application, ApplicationStatus
from core.config import get_settings
from core.exceptions import SlotNotFoundError, VFSBotError

# Тип callback-уведомителя: принимает telegram_id и текст сообщения.
Notifier = Callable[[int, str], Awaitable[None]]


class SlotChecker:
    """Фоновый планировщик проверки и бронирования слотов.

    Args:
        database: Слой доступа к данным.
        vfs_client: Клиент VFS Global.
        notifier: Корутина уведомления пользователя (telegram_id, текст).
    """

    def __init__(
        self,
        database: Database,
        vfs_client: VFSClient,
        notifier: Notifier,
    ) -> None:
        self._db = database
        self._client = vfs_client
        self._notify = notifier
        self._settings = get_settings()
        self._scheduler = AsyncIOScheduler()
        # Идентификаторы заявок, обрабатываемых в данный момент.
        self._in_progress: set[int] = set()

    def start(self) -> None:
        """Запустить планировщик с интервалом из настроек."""
        self._scheduler.add_job(
            self._check_all,
            trigger="interval",
            seconds=self._settings.check_interval_seconds,
            id="check_slots",
            max_instances=1,        # не запускать новый прогон, пока идёт прежний
            coalesce=True,          # схлопывать пропущенные запуски
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info(
            "Планировщик запущен (интервал {} сек)",
            self._settings.check_interval_seconds,
        )

    def shutdown(self) -> None:
        """Остановить планировщик."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Планировщик остановлен")

    async def _check_all(self) -> None:
        """Обойти все активные заявки и обработать каждую."""
        applications = await self._db.get_active_applications()
        if not applications:
            logger.debug("Активных заявок нет — пропуск прогона")
            return

        logger.info("Прогон проверки: {} активных заявок", len(applications))
        for application in applications:
            if application.id in self._in_progress:
                continue  # заявка уже обрабатывается
            await self._process_application(application)

    async def _process_application(self, application: Application) -> None:
        """Обработать одну заявку: найти слот и забронировать.

        Args:
            application: Активная заявка для обработки.
        """
        self._in_progress.add(application.id)
        try:
            # Переводим заявку в статус «поиск».
            await self._db.set_status(application.id, ApplicationStatus.SEARCHING)

            applicant = self._build_applicant_dict(application)
            result = await self._client.book_slot(
                applicant=applicant,
                start_date=application.start_date,
                end_date=application.end_date,
            )

            # Бронирование успешно — сохраняем реквизиты и уведомляем.
            await self._db.mark_booked(
                application.id,
                booked_date=result.slot_date,
                booked_time=result.slot_time,
                booking_reference=result.reference,
            )
            await self._notify(
                application.user.telegram_id,
                f"✅ Заявка №{application.id}: запись выполнена!\n"
                f"Дата: {result.slot_date.strftime('%d.%m.%Y')}, "
                f"время: {result.slot_time}\n"
                f"Номер бронирования: {result.reference}",
            )

        except SlotNotFoundError:
            # Слотов пока нет — оставляем заявку активной до следующего прогона.
            logger.debug("Заявка №{}: слотов пока нет", application.id)
            await self._db.set_status(application.id, ApplicationStatus.WAITING)

        except VFSBotError as exc:
            # Доменная ошибка — помечаем заявку как ошибочную и уведомляем.
            logger.warning("Заявка №{}: ошибка обработки: {}", application.id, exc)
            await self._db.set_status(application.id, ApplicationStatus.ERROR)
            await self._safe_notify(
                application.user.telegram_id,
                f"⚠️ Заявка №{application.id}: при обработке возникла ошибка. "
                f"Подробности: {exc}",
            )

        except Exception as exc:  # noqa: BLE001 - не даём упасть планировщику
            logger.exception("Заявка №{}: непредвиденная ошибка: {}",
                             application.id, exc)
            await self._db.set_status(application.id, ApplicationStatus.ERROR)

        finally:
            self._in_progress.discard(application.id)

    async def _safe_notify(self, telegram_id: int, text: str) -> None:
        """Уведомить пользователя, подавляя ошибки доставки.

        Args:
            telegram_id: Идентификатор пользователя.
            text: Текст уведомления.
        """
        try:
            await self._notify(telegram_id, text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось отправить уведомление: {}", exc)

    @staticmethod
    def _build_applicant_dict(application: Application) -> dict:
        """Сформировать словарь персональных данных для VFS-клиента.

        Args:
            application: Заявка с персональными данными.

        Returns:
            dict: Данные заявителя.
        """
        return {
            "surname": application.surname,
            "name": application.name,
            "birth_date": application.birth_date,
            "passport_number": application.passport_number,
            "passport_issue_date": application.passport_issue_date,
            "passport_expiry_date": application.passport_expiry_date,
            "email": application.email,
            "phone": application.phone,
        }
