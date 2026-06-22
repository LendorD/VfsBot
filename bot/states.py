"""Состояния конечного автомата (FSM) для пошагового сбора данных.

Используется aiogram FSM. Каждая группа состояний описывает отдельный
сценарий диалога: создание заявки (``/add``) и её редактирование (``/edit``).
"""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AddApplication(StatesGroup):
    """Состояния пошагового создания заявки командой ``/add``.

    Порядок состояний соответствует порядку запрашиваемых полей.
    """

    waiting_for_dates = State()            # ожидание диапазона дат
    waiting_for_surname = State()          # фамилия (латиницей)
    waiting_for_name = State()             # имя (латиницей)
    waiting_for_birth_date = State()       # дата рождения
    waiting_for_passport = State()         # номер паспорта
    waiting_for_passport_issue = State()   # дата выдачи паспорта
    waiting_for_passport_expiry = State()  # дата окончания паспорта
    waiting_for_email = State()            # email
    waiting_for_phone = State()            # телефон
    confirmation = State()                 # подтверждение всех данных


class EditApplication(StatesGroup):
    """Состояния редактирования заявки командой ``/edit``."""

    choosing_application = State()  # выбор заявки из списка
    choosing_field = State()        # выбор поля для изменения
    waiting_for_value = State()     # ввод нового значения выбранного поля
