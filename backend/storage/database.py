"""Слой доступа к данным (CRUD) поверх асинхронного SQLAlchemy.

Содержит:
    * фабрику движка и сессий;
    * класс :class:`Database` с методами создания/чтения/обновления/удаления
      пользователей и заявок.

Все методы асинхронные и работают через отдельную сессию на операцию,
что безопасно при конкурентном доступе из бота и планировщика.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import selectinload

from storage.models import (
    Application,
    ApplicationStatus,
    Base,
    User,
)
from core.exceptions import ApplicationNotFoundError, DatabaseError


class Database:
    """Высокоуровневый интерфейс работы с базой данных.

    Инкапсулирует движок и фабрику сессий, предоставляя удобные
    асинхронные методы для бизнес-логики бота.
    """

    def __init__(self, database_url: str) -> None:
        """Инициализировать движок и фабрику сессий.

        Args:
            database_url: Строка подключения (драйвер asyncpg).
        """
        self._engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
        )

    async def create_tables(self) -> None:
        """Создать таблицы в БД, если они ещё не существуют.

        В продакшене предпочтительнее использовать миграции Alembic, но для
        первичного запуска достаточно ``create_all``.
        """
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Таблицы базы данных проверены/созданы")

    async def dispose(self) -> None:
        """Корректно закрыть пул соединений при остановке приложения."""
        await self._engine.dispose()
        logger.info("Пул соединений с БД закрыт")

    # ------------------------------------------------------------------ #
    # Пользователи
    # ------------------------------------------------------------------ #
    async def get_or_create_user(
        self, telegram_id: int, username: str | None
    ) -> User:
        """Найти пользователя по Telegram ID или создать нового.

        Args:
            telegram_id: Идентификатор пользователя в Telegram.
            username: Username пользователя (может быть None).

        Returns:
            User: Существующий или только что созданный пользователь.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if user is None:
                user = User(telegram_id=telegram_id, username=username)
                session.add(user)
                await session.commit()
                await session.refresh(user)
                logger.info("Создан новый пользователь telegram_id={}", telegram_id)
            return user

    # ------------------------------------------------------------------ #
    # Заявки
    # ------------------------------------------------------------------ #
    async def create_application(
        self, telegram_id: int, username: str | None, data: dict
    ) -> Application:
        """Создать новую заявку для пользователя.

        Args:
            telegram_id: Идентификатор пользователя в Telegram.
            username: Username пользователя.
            data: Словарь с полями заявки (даты, персональные данные).

        Returns:
            Application: Сохранённая заявка с присвоенным id.

        Raises:
            DatabaseError: При ошибке записи в БД.
        """
        try:
            user = await self.get_or_create_user(telegram_id, username)
            async with self._session_factory() as session:
                application = Application(user_id=user.id, **data)
                session.add(application)
                await session.commit()
                await session.refresh(application)
                logger.info(
                    "Создана заявка №{} для пользователя {}",
                    application.id,
                    telegram_id,
                )
                return application
        except Exception as exc:  # noqa: BLE001 - оборачиваем в доменную ошибку
            logger.exception("Ошибка создания заявки: {}", exc)
            raise DatabaseError("Не удалось создать заявку") from exc

    async def get_application(self, application_id: int) -> Application:
        """Получить заявку по идентификатору.

        Args:
            application_id: Номер заявки.

        Returns:
            Application: Найденная заявка.

        Raises:
            ApplicationNotFoundError: Если заявка не найдена.
        """
        async with self._session_factory() as session:
            application = await session.get(Application, application_id)
            if application is None:
                raise ApplicationNotFoundError(
                    f"Заявка №{application_id} не найдена"
                )
            return application

    async def get_user_applications(
        self, telegram_id: int, only_active: bool = False
    ) -> Sequence[Application]:
        """Получить все заявки пользователя.

        Args:
            telegram_id: Идентификатор пользователя в Telegram.
            only_active: Если True — вернуть только активные заявки
                (не отменённые и не выполненные).

        Returns:
            Последовательность заявок, отсортированная по id.
        """
        async with self._session_factory() as session:
            query = (
                select(Application)
                .join(User)
                .where(User.telegram_id == telegram_id)
                .order_by(Application.id)
            )
            if only_active:
                query = query.where(
                    Application.status.in_(
                        [
                            ApplicationStatus.WAITING,
                            ApplicationStatus.SEARCHING,
                            ApplicationStatus.FOUND,
                        ]
                    )
                )
            result = await session.execute(query)
            return result.scalars().all()

    async def get_active_applications(self) -> Sequence[Application]:
        """Получить все активные заявки во всей системе.

        Используется планировщиком для периодической проверки слотов.

        Returns:
            Последовательность активных заявок.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(Application)
                # Жадно подгружаем пользователя, чтобы telegram_id был доступен
                # после закрытия сессии (планировщик уведомляет по нему).
                .options(selectinload(Application.user))
                .where(
                    Application.status.in_(
                        [ApplicationStatus.WAITING, ApplicationStatus.SEARCHING]
                    )
                )
            )
            return result.scalars().all()

    async def update_application(self, application_id: int, **fields) -> Application:
        """Обновить произвольные поля заявки.

        Args:
            application_id: Номер заявки.
            **fields: Пары «поле=значение» для обновления.

        Returns:
            Application: Обновлённая заявка.

        Raises:
            ApplicationNotFoundError: Если заявка не найдена.
        """
        async with self._session_factory() as session:
            application = await session.get(Application, application_id)
            if application is None:
                raise ApplicationNotFoundError(
                    f"Заявка №{application_id} не найдена"
                )
            for key, value in fields.items():
                setattr(application, key, value)
            await session.commit()
            await session.refresh(application)
            logger.info("Заявка №{} обновлена: {}", application_id, list(fields))
            return application

    async def set_status(
        self, application_id: int, status: ApplicationStatus
    ) -> Application:
        """Изменить статус заявки.

        Args:
            application_id: Номер заявки.
            status: Новый статус.

        Returns:
            Application: Обновлённая заявка.
        """
        return await self.update_application(application_id, status=status)

    async def mark_booked(
        self,
        application_id: int,
        booked_date: date,
        booked_time: str,
        booking_reference: str,
    ) -> Application:
        """Отметить заявку как успешно записанную.

        Args:
            application_id: Номер заявки.
            booked_date: Дата записи.
            booked_time: Время записи.
            booking_reference: Номер бронирования.

        Returns:
            Application: Обновлённая заявка со статусом ``booked``.
        """
        return await self.update_application(
            application_id,
            status=ApplicationStatus.BOOKED,
            booked_date=booked_date,
            booked_time=booked_time,
            booking_reference=booking_reference,
        )

    async def delete_application(self, application_id: int) -> None:
        """Удалить заявку из БД.

        Args:
            application_id: Номер заявки.

        Raises:
            ApplicationNotFoundError: Если заявка не найдена.
        """
        async with self._session_factory() as session:
            application = await session.get(Application, application_id)
            if application is None:
                raise ApplicationNotFoundError(
                    f"Заявка №{application_id} не найдена"
                )
            await session.delete(application)
            await session.commit()
            logger.info("Заявка №{} удалена", application_id)
