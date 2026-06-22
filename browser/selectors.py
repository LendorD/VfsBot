"""CSS/XPath-селекторы элементов сайта VFS Global.

ВНИМАНИЕ: значения ниже — заглушки (placeholder). Реальная вёрстка VFS
Global закрыта анти-бот защитой и периодически меняется, поэтому актуальные
селекторы необходимо определить вручную через DevTools на конкретном
визовом центре и страны подачи.

Селекторы вынесены в отдельный модуль, чтобы их можно было править, не
затрагивая логику клиента (:mod:`browser.client`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LoginSelectors:
    """Селекторы страницы авторизации в личный кабинет VFS."""

    email_input: str = "input#email"               # поле ввода email
    password_input: str = "input#password"         # поле ввода пароля
    submit_button: str = "button[type='submit']"   # кнопка «Войти»
    error_banner: str = ".alert-danger"            # баннер ошибки авторизации


@dataclass(frozen=True)
class BookingSelectors:
    """Селекторы страниц выбора центра, услуги и слота."""

    visa_center_dropdown: str = "select#centerCode"     # выбор визового центра
    category_dropdown: str = "select#loginUser"         # категория визы
    subcategory_dropdown: str = "select#urn"            # подкатегория
    continue_button: str = "button#btnContinue"         # кнопка «Продолжить»

    # Календарь и слоты
    calendar_container: str = ".vfs-calendar"           # контейнер календаря
    available_day: str = ".day.available"               # доступный день
    day_by_date: str = "td[data-date='{date}']"         # день по дате (ISO)
    time_slot: str = ".time-slot.available"             # доступный временной слот
    no_slots_message: str = ".no-appointments"          # сообщение «нет слотов»


@dataclass(frozen=True)
class ApplicantFormSelectors:
    """Селекторы формы персональных данных заявителя."""

    surname_input: str = "input[name='surname']"
    first_name_input: str = "input[name='firstName']"
    birth_date_input: str = "input[name='dateOfBirth']"
    passport_number_input: str = "input[name='passportNumber']"
    passport_issue_input: str = "input[name='passportIssueDate']"
    passport_expiry_input: str = "input[name='passportExpiryDate']"
    email_input: str = "input[name='email']"
    phone_input: str = "input[name='contactNumber']"
    submit_button: str = "button#submitApplicant"


@dataclass(frozen=True)
class CaptchaSelectors:
    """Селекторы блока капчи."""

    captcha_image: str = "img.captcha-image"      # изображение капчи
    captcha_input: str = "input#captchaCode"      # поле ввода кода
    recaptcha_frame: str = "iframe[src*='recaptcha']"  # фрейм reCAPTCHA


@dataclass(frozen=True)
class ConfirmationSelectors:
    """Селекторы страницы подтверждения брони."""

    booking_reference: str = ".booking-reference"  # номер бронирования
    confirmed_date: str = ".confirmed-date"        # подтверждённая дата
    confirmed_time: str = ".confirmed-time"        # подтверждённое время


# Готовые экземпляры для импорта в клиенте.
LOGIN = LoginSelectors()
BOOKING = BookingSelectors()
APPLICANT_FORM = ApplicantFormSelectors()
CAPTCHA = CaptchaSelectors()
CONFIRMATION = ConfirmationSelectors()
