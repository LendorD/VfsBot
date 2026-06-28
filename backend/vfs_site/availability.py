"""Чтение доступности слотов на шаге 1 VFS.

После выбора центра/категории/подкатегории VFS показывает сообщение:
  • «...нет доступных слотов для записи...» — слотов нет;
  • «Ближайший доступный слот для N заявителей : ДД/ММ/ГГГГ» — есть (по одной
    строке на каждое число заявителей).

Это сообщение — основной сигнал для поиска свободных дат: его читает и бот,
и (в будущем) веб-бэкенд. Функция универсальна — принимает Playwright Page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from playwright.async_api import Page

# «...для 2 заявителей : 14/07/2026»
_NEAREST_RE = re.compile(
    r"для\s+(\d+)\s+заявител\w*\s*:?\s*(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
_NO_SLOTS_MARKERS = (
    "нет доступных слотов",
    "no appointment slots",
    "попробуйте позже",
)


@dataclass
class Availability:
    """Результат чтения доступности.

    Attributes:
        has_slots: Есть ли свободные слоты.
        nearest: Ближайшая дата по числу заявителей ({1: date, 2: date}).
        recognized: Удалось ли вообще распознать сообщение о доступности.
        raw: Фрагмент исходного текста (для отладки).
    """

    has_slots: bool = False
    nearest: dict[int, date] = field(default_factory=dict)
    recognized: bool = False
    raw: str = ""


async def read_availability(page: Page) -> Availability:
    """Прочитать сообщение о доступности слотов на текущей странице."""
    try:
        text = await page.locator("body").inner_text(timeout=5_000)
    except Exception:  # noqa: BLE001
        return Availability()

    low = text.lower()

    nearest: dict[int, date] = {}
    for match in _NEAREST_RE.finditer(text):
        count = int(match.group(1))
        try:
            slot_date = datetime.strptime(match.group(2), "%d/%m/%Y").date()
        except ValueError:
            continue
        nearest[count] = slot_date

    if nearest:
        return Availability(
            has_slots=True, nearest=nearest, recognized=True, raw=text[:300]
        )

    if any(marker in low for marker in _NO_SLOTS_MARKERS):
        return Availability(has_slots=False, recognized=True, raw="нет доступных слотов")

    return Availability(recognized=False, raw=text[:200])


def matches_desired(
    avail: Availability,
    applicants: int = 1,
    start: date | None = None,
    end: date | None = None,
) -> date | None:
    """Вернуть найденную дату, если она подходит под желаемые условия.

    Args:
        avail: Результат чтения доступности.
        applicants: Для какого числа заявителей нужна дата.
        start: Нижняя граница желаемого диапазона (включительно) или None.
        end: Верхняя граница желаемого диапазона (включительно) или None.

    Returns:
        Подходящую дату или None.
    """
    slot = avail.nearest.get(applicants)
    if slot is None:
        return None
    if start is not None and slot < start:
        return None
    if end is not None and slot > end:
        return None
    return slot
