"""CSS/XPath-селекторы элементов сайта VFS Global.

ВНИМАНИЕ: значения ниже — заглушки (placeholder). Реальная вёрстка VFS
Global закрыта анти-бот защитой и периодически меняется, поэтому актуальные
селекторы необходимо определить вручную через DevTools на конкретном
визовом центре и страны подачи.

Селекторы вынесены в отдельный модуль, чтобы их можно было править, не
затрагивая логику клиента (:mod:`vfs_site.client`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartPageSelectors:
    """Селекторы стартовой страницы визового центра (Россия → Франция)."""

    # Кнопка «Записаться сейчас» на главной странице.
    book_now_button: str = "#action-link-2 > span"


@dataclass(frozen=True)
class WelcomeSelectors:
    """Селекторы страницы «Добро пожаловать в систему записи VFS».

    Здесь два свёрнутых блока («НЕ заполнили» / «УЖЕ заполнили анкету
    France-Visas»). Чтобы добраться до кнопки записи, нужно сначала раскрыть
    блок кнопкой «Подробнее».
    """

    # «Подробнее» — раскрывает свёрнутый блок с дальнейшими действиями.
    viewmore_button: str = (
        "#__next > div > div > div:nth-child(3) > "
        "div.row.no-gutters.collapsible-row.border-0 > div.viewmore.collapsed"
    )
    # Кнопка/ссылка внутри раскрытого блока, ведущая к записи.
    # ВНИМАНИЕ: nth-child(54) — хрупкий индекс, при изменении вёрстки «съедет».
    proceed_button: str = "#colap1 > div > p:nth-child(54) > a"


@dataclass(frozen=True)
class LoginSelectors:
    """Селекторы страницы авторизации в личный кабинет VFS."""

    email_input: str = "#email"                    # поле ввода email
    password_input: str = "#password"              # поле ввода пароля
    submit_button: str = (                         # кнопка «Войти»
        "body > app-root > div > main > div > app-login > section > "
        "div > div > mat-card > form > button"
    )
    error_banner: str = ".alert-danger"            # баннер ошибки авторизации


@dataclass(frozen=True)
class DashboardSelectors:
    """Селекторы личного кабинета после входа."""

    # Кнопка «Записаться на прием» на странице со списком записей.
    book_appointment_button: str = (
        "body > app-root > div > main > div > app-dashboard > "
        "section.container.py-15.py-md-30.d-block > div > "
        "div.position-relative > div > button > span.mdc-button__label"
    )


@dataclass(frozen=True)
class ApplicationDetailSelectors:
    """Селекторы шага 1 «Информация о подаче документов».

    Три выпадающих списка Angular Material. ID присваиваются по порядку
    создания компонентов; на этой странице соответствие такое (нестандартное):
    центр — mat-select-0, подкатегория — mat-select-1, категория — mat-select-2.
    """

    center_select: str = "#mat-select-0"        # Центр приложений
    subcategory_select: str = "#mat-select-1"   # Подкатегория
    category_select: str = "#mat-select-2"      # Категория записи


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
START_PAGE = StartPageSelectors()
WELCOME = WelcomeSelectors()
LOGIN = LoginSelectors()
DASHBOARD = DashboardSelectors()
APP_DETAIL = ApplicationDetailSelectors()
BOOKING = BookingSelectors()
APPLICANT_FORM = ApplicantFormSelectors()
CAPTCHA = CaptchaSelectors()
CONFIRMATION = ConfirmationSelectors()
