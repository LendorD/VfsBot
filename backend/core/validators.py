"""Валидаторы пользовательского ввода.

Содержит функции проверки и нормализации:
    * дат и диапазонов дат;
    * email;
    * международного номера телефона;
    * имён/фамилий латиницей;
    * номера паспорта.

Все функции при ошибке выбрасывают :class:`ValidationError`
(или её наследника) с понятным сообщением на русском.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from core.exceptions import DateRangeError, ValidationError

# Формат дат, используемый во всех командах бота.
DATE_FORMAT = "%d.%m.%Y"

# --- Регулярные выражения ---
# Email по упрощённому, но практичному шаблону.
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
# Международный телефон: необязательный «+» и 7–15 цифр (стандарт E.164).
_PHONE_RE = re.compile(r"^\+?[1-9]\d{6,14}$")
# Имя/фамилия латиницей: буквы, пробел, дефис и апостроф.
_LATIN_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z\-' ]{0,99}$")
# Номер паспорта: латинские буквы и цифры, 5–20 символов.
_PASSPORT_RE = re.compile(r"^[A-Za-z0-9]{5,20}$")


def parse_date(value: str, *, allow_past: bool = True) -> date:
    """Разобрать и проверить дату в формате ДД.ММ.ГГГГ.

    Args:
        value: Строка с датой.
        allow_past: Разрешить ли даты в прошлом. Для дат рождения и выдачи
            паспорта — True, для дат записи — False.

    Returns:
        date: Распарсенная дата.

    Raises:
        ValidationError: Если формат некорректен или дата в прошлом при
            ``allow_past=False``.
    """
    value = value.strip()
    try:
        parsed = datetime.strptime(value, DATE_FORMAT).date()
    except ValueError as exc:
        raise ValidationError(
            f"Некорректная дата «{value}». Ожидается формат ДД.ММ.ГГГГ."
        ) from exc

    if not allow_past and parsed < date.today():
        raise ValidationError(
            f"Дата «{value}» уже в прошлом. Укажите сегодняшнюю или будущую дату."
        )
    return parsed


def parse_date_range(value: str) -> tuple[date, date]:
    """Разобрать диапазон дат вида ДД.ММ.ГГГГ-ДД.ММ.ГГГГ.

    Начальная дата не может быть в прошлом, а конечная — раньше начальной.

    Args:
        value: Строка с диапазоном дат.

    Returns:
        Кортеж (start_date, end_date).

    Raises:
        DateRangeError: Если формат диапазона или порядок дат некорректны.
        ValidationError: Если начальная дата в прошлом.
    """
    raw = value.strip().replace(" ", "")
    # Разделитель «-» между двумя датами формата ДД.ММ.ГГГГ.
    parts = raw.split("-")
    if len(parts) != 2:
        raise DateRangeError(
            "Диапазон должен быть в формате ДД.ММ.ГГГГ-ДД.ММ.ГГГГ."
        )

    start = parse_date(parts[0], allow_past=False)
    end = parse_date(parts[1], allow_past=False)

    if end < start:
        raise DateRangeError(
            "Конечная дата диапазона не может быть раньше начальной."
        )
    return start, end


def validate_email(value: str) -> str:
    """Проверить и нормализовать email.

    Args:
        value: Введённый email.

    Returns:
        str: Email в нижнем регистре без пробелов.

    Raises:
        ValidationError: Если email не соответствует шаблону.
    """
    email = value.strip().lower()
    if not _EMAIL_RE.match(email):
        raise ValidationError(f"Некорректный email: «{value}».")
    return email


def validate_phone(value: str) -> str:
    """Проверить и нормализовать международный номер телефона.

    Удаляет пробелы, скобки и дефисы, после чего проверяет по стандарту E.164.

    Args:
        value: Введённый телефон.

    Returns:
        str: Нормализованный номер (только «+» и цифры).

    Raises:
        ValidationError: Если номер не соответствует формату.
    """
    cleaned = re.sub(r"[\s()\-]", "", value.strip())
    if not _PHONE_RE.match(cleaned):
        raise ValidationError(
            f"Некорректный телефон: «{value}». Пример: +79991234567."
        )
    return cleaned


def validate_latin_name(value: str, field_name: str = "Имя") -> str:
    """Проверить имя или фамилию, записанные латиницей.

    Args:
        value: Введённое значение.
        field_name: Название поля для сообщения об ошибке.

    Returns:
        str: Значение с убранными крайними пробелами.

    Raises:
        ValidationError: Если значение содержит недопустимые символы.
    """
    name = value.strip()
    if not _LATIN_NAME_RE.match(name):
        raise ValidationError(
            f"{field_name} должно быть указано латиницей (только буквы). "
            f"Получено: «{value}»."
        )
    return name


def validate_passport(value: str) -> str:
    """Проверить номер паспорта.

    Args:
        value: Введённый номер паспорта.

    Returns:
        str: Номер в верхнем регистре без пробелов.

    Raises:
        ValidationError: Если номер не соответствует шаблону.
    """
    passport = re.sub(r"\s", "", value.strip()).upper()
    if not _PASSPORT_RE.match(passport):
        raise ValidationError(
            f"Некорректный номер паспорта: «{value}». "
            "Допустимы латинские буквы и цифры (5–20 символов)."
        )
    return passport
