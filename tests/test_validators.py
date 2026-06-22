"""Юнит-тесты валидаторов пользовательского ввода."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from utils.exceptions import DateRangeError, ValidationError
from utils.validators import (
    parse_date,
    parse_date_range,
    validate_email,
    validate_latin_name,
    validate_passport,
    validate_phone,
)

# Дата заведомо в будущем — для тестов диапазонов.
_FUTURE = date.today() + timedelta(days=10)
_FUTURE_STR = _FUTURE.strftime("%d.%m.%Y")
_FUTURE2 = date.today() + timedelta(days=20)
_FUTURE2_STR = _FUTURE2.strftime("%d.%m.%Y")


class TestParseDate:
    """Тесты разбора одиночной даты."""

    def test_valid_past_date(self) -> None:
        """Дата в прошлом допустима при allow_past=True."""
        assert parse_date("01.01.1990", allow_past=True) == date(1990, 1, 1)

    def test_invalid_format_raises(self) -> None:
        """Некорректный формат вызывает ValidationError."""
        with pytest.raises(ValidationError):
            parse_date("1990/01/01")

    def test_past_date_disallowed(self) -> None:
        """Прошедшая дата запрещена при allow_past=False."""
        with pytest.raises(ValidationError):
            parse_date("01.01.2000", allow_past=False)

    def test_nonexistent_date_raises(self) -> None:
        """Несуществующая дата (32 число) вызывает ошибку."""
        with pytest.raises(ValidationError):
            parse_date("32.01.2030")


class TestParseDateRange:
    """Тесты разбора диапазона дат."""

    def test_valid_range(self) -> None:
        """Корректный диапазон разбирается в кортеж дат."""
        start, end = parse_date_range(f"{_FUTURE_STR}-{_FUTURE2_STR}")
        assert start == _FUTURE
        assert end == _FUTURE2

    def test_range_with_spaces(self) -> None:
        """Пробелы вокруг дат игнорируются."""
        start, end = parse_date_range(f" {_FUTURE_STR} - {_FUTURE2_STR} ")
        assert start == _FUTURE
        assert end == _FUTURE2

    def test_end_before_start_raises(self) -> None:
        """Конечная дата раньше начальной — ошибка диапазона."""
        with pytest.raises(DateRangeError):
            parse_date_range(f"{_FUTURE2_STR}-{_FUTURE_STR}")

    def test_missing_separator_raises(self) -> None:
        """Отсутствие разделителя вызывает ошибку диапазона."""
        with pytest.raises(DateRangeError):
            parse_date_range(_FUTURE_STR)


class TestValidateEmail:
    """Тесты валидации email."""

    @pytest.mark.parametrize(
        "value",
        ["user@example.com", "John.Doe+tag@mail.co.uk", "a_b@d.io"],
    )
    def test_valid_emails(self, value: str) -> None:
        """Корректные адреса проходят и нормализуются в нижний регистр."""
        assert validate_email(value) == value.strip().lower()

    @pytest.mark.parametrize(
        "value", ["plainaddress", "user@", "@domain.com", "user@domain"]
    )
    def test_invalid_emails(self, value: str) -> None:
        """Некорректные адреса вызывают ValidationError."""
        with pytest.raises(ValidationError):
            validate_email(value)


class TestValidatePhone:
    """Тесты валидации телефона."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("+7 (999) 123-45-67", "+79991234567"),
            ("+44 20 7946 0958", "+442079460958"),
            ("79991234567", "79991234567"),
        ],
    )
    def test_valid_phones(self, raw: str, expected: str) -> None:
        """Телефон нормализуется к формату E.164."""
        assert validate_phone(raw) == expected

    @pytest.mark.parametrize("value", ["12345", "abcdefg", "+0123"])
    def test_invalid_phones(self, value: str) -> None:
        """Некорректные номера вызывают ValidationError."""
        with pytest.raises(ValidationError):
            validate_phone(value)


class TestValidateLatinName:
    """Тесты валидации имени/фамилии латиницей."""

    @pytest.mark.parametrize("value", ["Ivanov", "Mary-Jane", "O'Brien"])
    def test_valid_names(self, value: str) -> None:
        """Латинские имена с дефисом/апострофом допустимы."""
        assert validate_latin_name(value) == value

    @pytest.mark.parametrize("value", ["Иванов", "123", "@name"])
    def test_invalid_names(self, value: str) -> None:
        """Кириллица и спецсимволы недопустимы."""
        with pytest.raises(ValidationError):
            validate_latin_name(value)


class TestValidatePassport:
    """Тесты валидации номера паспорта."""

    def test_valid_passport_normalized(self) -> None:
        """Номер приводится к верхнему регистру без пробелов."""
        assert validate_passport("ab 123456") == "AB123456"

    @pytest.mark.parametrize("value", ["123", "пасп123", "!!!"])
    def test_invalid_passport(self, value: str) -> None:
        """Слишком короткий или некорректный номер — ошибка."""
        with pytest.raises(ValidationError):
            validate_passport(value)
