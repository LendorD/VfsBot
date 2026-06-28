"""Юнит-тесты браузерного клиента VFS и связанных структур.

Поскольку реальное взаимодействие с сайтом VFS не реализовано (каркас),
тесты покрывают:
    * структуры данных результата (AvailableSlot, BookingResult);
    * поведение заглушки решателя капчи;
    * формирование словаря заявителя планировщиком.
"""

from __future__ import annotations

from datetime import date

import pytest

from captcha.solver import StubCaptchaSolver, get_captcha_solver
from vfs_site.client import AvailableSlot, BookingResult
from scheduler.checker import SlotChecker
from storage.models import Application, ApplicationStatus
from core.exceptions import CaptchaError


class TestSlotDataclasses:
    """Тесты структур данных слота и брони."""

    def test_available_slot_fields(self) -> None:
        """AvailableSlot хранит дату и время."""
        slot = AvailableSlot(slot_date=date(2030, 7, 1), slot_time="10:30")
        assert slot.slot_date == date(2030, 7, 1)
        assert slot.slot_time == "10:30"

    def test_booking_result_fields(self) -> None:
        """BookingResult хранит дату, время и номер брони."""
        result = BookingResult(
            slot_date=date(2030, 7, 1), slot_time="10:30", reference="ABC123"
        )
        assert result.reference == "ABC123"


class TestCaptchaSolver:
    """Тесты заглушки решателя капчи."""

    def test_factory_returns_stub(self) -> None:
        """Фабрика возвращает заглушку независимо от ключа."""
        assert isinstance(get_captcha_solver(None), StubCaptchaSolver)
        assert isinstance(get_captcha_solver("some-key"), StubCaptchaSolver)

    @pytest.mark.asyncio
    async def test_image_captcha_raises(self) -> None:
        """Решение графической капчи не реализовано — CaptchaError."""
        solver = StubCaptchaSolver()
        with pytest.raises(CaptchaError):
            await solver.solve_image_captcha(b"fake-image")

    @pytest.mark.asyncio
    async def test_recaptcha_raises(self) -> None:
        """Решение reCAPTCHA не реализовано — CaptchaError."""
        solver = StubCaptchaSolver()
        with pytest.raises(CaptchaError):
            await solver.solve_recaptcha("site-key", "https://example.com")


class TestApplicantDict:
    """Тесты формирования словаря заявителя для VFS-клиента."""

    def test_build_applicant_dict(self) -> None:
        """Словарь содержит все персональные поля заявки."""
        application = Application(
            id=1,
            user_id=1,
            start_date=date(2030, 7, 1),
            end_date=date(2030, 7, 15),
            status=ApplicationStatus.WAITING,
            surname="Ivanov",
            name="Ivan",
            birth_date=date(1990, 1, 1),
            passport_number="AB123456",
            passport_issue_date=date(2020, 1, 1),
            passport_expiry_date=date(2030, 1, 1),
            email="ivan@example.com",
            phone="+79991234567",
        )

        result = SlotChecker._build_applicant_dict(application)

        assert result["surname"] == "Ivanov"
        assert result["name"] == "Ivan"
        assert result["passport_number"] == "AB123456"
        assert result["email"] == "ivan@example.com"
        assert result["phone"] == "+79991234567"
        assert set(result.keys()) == {
            "surname",
            "name",
            "birth_date",
            "passport_number",
            "passport_issue_date",
            "passport_expiry_date",
            "email",
            "phone",
        }
