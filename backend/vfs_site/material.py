"""Утилиты для выпадающих списков Angular Material (mat-select).

Функции универсальны и НЕ зависят от конкретной страницы: принимают
Playwright ``Page`` и селектор-триггер списка. Их используют и интерактивный
``inspect_page.py``, и боевой ``VFSClient``.

Это сделано осознанно: выбор центра/категории/подкатегории должен управляться
параметрами «задачи» (center/category/subcategory), которые могут приходить
как из Telegram-бота, так и из будущего веб-интерфейса. Логика выбора — здесь,
в одном месте; источники параметров — снаружи.
"""

from __future__ import annotations

from loguru import logger
from playwright.async_api import Page

# В открытой панели Angular Material опции помечены role="option".
_OPTION_SELECTOR = '[role="option"]'


async def open_dropdown(page: Page, trigger: str, timeout: int = 15_000) -> None:
    """Открыть список mat-select по селектору-триггеру.

    Args:
        page: Страница Playwright.
        trigger: Селектор элемента mat-select (например, ``#mat-select-0``).
        timeout: Таймаут ожидания появления опций, мс.
    """
    await page.click(trigger)
    await page.wait_for_selector(_OPTION_SELECTOR, timeout=timeout)


async def get_options(page: Page) -> list[str]:
    """Вернуть тексты всех опций уже открытого списка."""
    loc = page.locator(_OPTION_SELECTOR)
    count = await loc.count()
    texts: list[str] = []
    for i in range(count):
        text = (await loc.nth(i).inner_text()).strip()
        if text:
            texts.append(text)
    return texts


async def select_by_text(page: Page, value: str, exact: bool = False) -> str | None:
    """Кликнуть опцию открытого списка по тексту.

    Сначала ищется точное совпадение, затем (если ``exact=False``) — частичное.

    Args:
        page: Страница Playwright.
        value: Искомый текст (как на сайте; регистр не важен).
        exact: Требовать точное совпадение.

    Returns:
        Текст выбранной опции или ``None``, если совпадение не найдено.
    """
    loc = page.locator(_OPTION_SELECTOR)
    count = await loc.count()
    needle = value.strip().casefold()
    partial_index: int | None = None
    partial_text: str | None = None

    for i in range(count):
        text = (await loc.nth(i).inner_text()).strip()
        haystack = text.casefold()
        if haystack == needle:
            await loc.nth(i).click()
            return text
        if not exact and partial_index is None and needle in haystack:
            partial_index, partial_text = i, text

    if partial_index is not None:
        await page.locator(_OPTION_SELECTOR).nth(partial_index).click()
        return partial_text
    return None


async def close_dropdown(page: Page) -> None:
    """Закрыть открытый список без выбора (Escape)."""
    try:
        await page.keyboard.press("Escape")
    except Exception:  # noqa: BLE001
        pass


async def read_options(page: Page, trigger: str) -> list[str]:
    """Открыть список, прочитать варианты и закрыть (без выбора).

    Удобно для UI: показать пользователю доступные центры/категории.
    """
    await open_dropdown(page, trigger)
    options = await get_options(page)
    await close_dropdown(page)
    logger.debug("Список {}: {} вариантов", trigger, len(options))
    return options


async def choose(page: Page, trigger: str, value: str, exact: bool = False) -> str | None:
    """Открыть список и выбрать опцию по тексту.

    Args:
        page: Страница Playwright.
        trigger: Селектор mat-select.
        value: Искомый текст опции.
        exact: Требовать точное совпадение.

    Returns:
        Текст выбранной опции или ``None``.
    """
    await open_dropdown(page, trigger)
    chosen = await select_by_text(page, value, exact=exact)
    if chosen is None:
        await close_dropdown(page)
        logger.warning("В списке {} не найдено: {}", trigger, value)
    else:
        logger.info("В списке {} выбрано: {}", trigger, chosen)
    return chosen
