"""Открыть VFS со страницы логина, войти и проиграть сценарий записи.

Запускается РЕАЛЬНЫЙ Chrome с постоянным профилем (каталог ``.browser_profile``):
профиль хранит cookie ``cf_clearance`` и сессию входа между запусками.

По умолчанию скрипт открывает страницу логина, заполняет почту/пароль из
``.env`` (``VFS_LOGIN`` / ``VFS_PASSWORD``), жмёт «Войти», затем «Записаться
на прием». Шаги входа «мягкие»: если вы уже авторизованы, они пропускаются.

При появлении Cloudflare скрипт ставит паузу — пройдите проверку вручную,
он дождётся и продолжит. Окно НЕ закрывается само.

Запуск:
    python inspect_page.py                 # логин + весь сценарий
    python inspect_page.py --steps 0        # только открыть логин, без действий
    python inspect_page.py --url <адрес>    # открыть другой стартовый URL
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from loguru import logger
from playwright.async_api import BrowserContext, Page

from vfs_site import availability, material, selectors
from vfs_site.browser import BrowserManager
from core.config import get_settings
from core.logger import setup_logger

# Каталог постоянного профиля Chrome (рядом со скриптом).
PROFILE_DIR = str(Path(__file__).resolve().parent / ".browser_profile")

# Файл со всеми доступными вариантами (источник выбора для бота/сайта).
OPTIONS_FILE = Path(__file__).resolve().parent / "data" / "vfs_options.json"

# Сценарий: вход + переход к записи. Каждый шаг — действие над селектором.
#   action="fill"  — ввести в поле значение из настроек (value_attr);
#   action="click" — кликнуть по элементу.
#   optional=True  — пропустить шаг, если элемента нет (напр., уже залогинены).
# Добавляйте новые шаги по мере того, как находите элементы следующих страниц.
STEPS: list[dict] = [
    {
        "action": "fill",
        "name": "Email",
        "selector": selectors.LOGIN.email_input,
        "value_attr": "vfs_login",
        "optional": True,
    },
    {
        "action": "fill",
        "name": "Пароль",
        "selector": selectors.LOGIN.password_input,
        "value_attr": "vfs_password",
        "optional": True,
    },
    {
        "action": "click",
        "name": "Войти",
        "selector": selectors.LOGIN.submit_button,
        "optional": True,
    },
    {
        "action": "click",
        "name": "Записаться на прием",
        "selector": selectors.DASHBOARD.book_appointment_button,
    },
    # Шаг 1 «Информация о подаче документов»: три зависимых списка.
    # Порядок важен: центр → категория → подкатегория (последняя зависит
    # от категории). Значения берутся из .env (VFS_CENTER/CATEGORY/SUBCATEGORY).
    {
        "action": "select",
        "name": "Центр приложений",
        "selector": selectors.APP_DETAIL.center_select,
        "value_attr": "vfs_center",
    },
    {
        "action": "select",
        "name": "Категория записи",
        "selector": selectors.APP_DETAIL.category_select,
        "value_attr": "vfs_category",
    },
    {
        "action": "select",
        "name": "Подкатегория",
        "selector": selectors.APP_DETAIL.subcategory_select,
        "value_attr": "vfs_subcategory",
    },
]


async def _current_page(context: BrowserContext, fallback: Page) -> Page:
    """Вернуть активную страницу (последнюю открытую вкладку)."""
    pages = [p for p in context.pages if not p.is_closed()]
    return pages[-1] if pages else fallback


async def _is_cloudflare(page: Page) -> bool:
    """Определить ПОЛНОЭКРАННУЮ проверку Cloudflare.

    Важно не путать её со встроенным виджетом «Успешно» на форме логина —
    поэтому ориентируемся на характерный текст страницы-заглушки, а не на
    наличие iframe Cloudflare (он есть и в обычном виджете формы).
    """
    try:
        title = (await page.title()).lower()
    except Exception:  # noqa: BLE001
        title = ""
    if "just a moment" in title:
        return True
    try:
        body = (await page.locator("body").inner_text(timeout=2000)).lower()
    except Exception:  # noqa: BLE001
        return False
    markers = (
        "выполнение проверки безопасности",
        "проверяет, что вы не бот",
        "checking your browser",
    )
    return any(m in body for m in markers)


async def _wait_if_cloudflare(page: Page, manager: BrowserManager) -> None:
    """При полноэкранной проверке Cloudflare ждать ручного прохождения."""
    if not await _is_cloudflare(page):
        return
    print(
        "\n[Cloudflare] Появилась проверка безопасности.\n"
        "  → Поставьте галочку «Подтвердите, что вы человек» в окне браузера\n"
        "    и дождитесь загрузки сайта. Я подожду до 5 минут...\n"
    )
    waited = 0.0
    while waited < 300 and manager.is_connected:
        await asyncio.sleep(1.0)
        waited += 1.0
        if not await _is_cloudflare(page):
            logger.info("Cloudflare пройден за ~{:.0f} с", waited)
            print("[Cloudflare] Проверка пройдена, продолжаю.\n")
            return
    print("[Cloudflare] Не дождался прохождения проверки (таймаут).\n")


async def _warn_if_blocked(page: Page) -> bool:
    """Распознать страницу блокировки VFS по IP (ошибка 403201)."""
    try:
        content = (await page.content()).lower()
    except Exception:  # noqa: BLE001
        return False
    if "403201" in content or "несанкционированная попытка" in content:
        print(
            "\n[VFS] Доступ заблокирован (ошибка 403201).\n"
            "      Это блокировка по IP на стороне VFS, НЕ связана со скриптом\n"
            "      (повторяется и при ручном заходе). Что делать:\n"
            "      • сменить сеть/IP: мобильный интернет, другой Wi-Fi, VPN;\n"
            "      • прописать резидентный прокси в .env (PROXY_SERVER);\n"
            "      • иногда помогает просто подождать пару часов.\n"
        )
        return True
    return False


async def _do_select(page: Page, step: dict, settings) -> bool:
    """Открыть mat-select, показать варианты и выбрать заданное значение.

    Returns:
        True — можно продолжать; False — остановиться (значение не задано
        или не найдено среди вариантов).
    """
    selector = step["selector"]
    name = step["name"]
    await material.open_dropdown(page, selector)
    options = await material.get_options(page)
    print(f"\nВарианты «{name}» ({len(options)}):")
    for opt in options:
        print(f"   • {opt}")

    value = getattr(settings, step["value_attr"], None)
    env_name = step["value_attr"].upper()
    if not value:
        await material.close_dropdown(page)
        print(
            f"\n[i] Значение для «{name}» не задано. Скопируйте нужное из списка\n"
            f"    выше и впишите в .env: {env_name}=...  затем перезапустите.\n"
        )
        return False

    chosen = await material.select_by_text(page, value)
    if chosen is None:
        await material.close_dropdown(page)
        print(
            f"\n[!] «{value}» не найдено среди вариантов «{name}». "
            f"Уточните {env_name} в .env.\n"
        )
        return False

    print(f"   → выбрано: {chosen}")
    await page.wait_for_timeout(1200)  # дать подгрузиться зависимым спискам
    return True


async def _dump_options(page: Page, settings) -> dict:
    """Собрать все доступные варианты шага 1 и вернуть их структурой.

    Центры читаются как есть; категории/подкатегории требуют выбранного
    центра, поэтому сначала выбирается центр (из .env или первый из списка),
    затем по каждой категории читаются её подкатегории.
    """
    centers = await material.read_options(page, selectors.APP_DETAIL.center_select)

    center_used = settings.vfs_center or (centers[0] if centers else None)
    if center_used:
        await material.choose(page, selectors.APP_DETAIL.center_select, center_used)
        await page.wait_for_timeout(1200)

    categories = await material.read_options(page, selectors.APP_DETAIL.category_select)

    subcategories: dict[str, list[str]] = {}
    for category in categories:
        await material.choose(page, selectors.APP_DETAIL.category_select, category)
        await page.wait_for_timeout(1500)
        subcategories[category] = await material.read_options(
            page, selectors.APP_DETAIL.subcategory_select
        )

    return {
        "center_used": center_used,
        "centers": centers,
        "categories": categories,
        "subcategories": subcategories,
    }


async def _run_steps(
    context: BrowserContext, page: Page, manager: BrowserManager, limit: int | None
) -> Page:
    """Выполнить шаги сценария по очереди."""
    settings = get_settings()
    steps = STEPS if limit is None else STEPS[:limit]

    for index, step in enumerate(steps, start=1):
        page = await _current_page(context, page)
        await _wait_if_cloudflare(page, manager)

        action = step.get("action", "click")
        selector = step["selector"]
        optional = step.get("optional", False)
        timeout = 10_000 if optional else settings.browser_timeout_ms
        logger.info("Шаг {}: «{}» [{}] → {}", index, step["name"], action, selector)

        try:
            await page.wait_for_selector(selector, timeout=timeout)
        except Exception:  # noqa: BLE001 - элемента нет
            if optional:
                logger.info("Шаг {} пропущен (элемента нет — вероятно, уже выполнено)", index)
                continue
            logger.error("Шаг {}: элемент не найден: {}", index, selector)
            print(f"\n[!] Шаг {index} «{step['name']}» — элемент не найден: {selector}\n")
            break

        try:
            if action == "fill":
                value = getattr(settings, step["value_attr"], None) or ""
                await page.fill(selector, value)
            elif action == "select":
                if not await _do_select(page, step, settings):
                    break
            else:
                await page.click(selector)
                await page.wait_for_timeout(1500)
                page = await _current_page(context, page)
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=15_000)
                except Exception:  # noqa: BLE001 - SPA может не триггерить load
                    pass
                await _wait_if_cloudflare(page, manager)
            logger.info("Шаг {} выполнен. Текущий URL: {}", index, page.url)
            if await _warn_if_blocked(page):
                break
        except Exception as exc:  # noqa: BLE001
            logger.error("Шаг {} не удался ({}): {}", index, selector, exc)
            print(f"\n[!] Шаг {index} «{step['name']}» не сработал: {selector}\n")
            break

    return page


async def _report_availability(page: Page) -> None:
    """Прочитать и напечатать доступность слотов (если страница это показывает)."""
    avail = await availability.read_availability(page)
    if not avail.recognized:
        return
    if not avail.has_slots:
        print("\n[Слоты] Свободных слотов сейчас нет.\n")
        return
    print("\n[Слоты] Найдены ближайшие доступные даты:")
    for count, slot_date in sorted(avail.nearest.items()):
        print(f"   • для {count} заявителей: {slot_date:%d.%m.%Y}")
    print()


def _warn_if_no_credentials() -> None:
    """Предупредить, если данные входа в .env не заполнены."""
    settings = get_settings()
    placeholders = {None, "", "user@example.com", "change_me"}
    if settings.vfs_login in placeholders or settings.vfs_password in placeholders:
        print(
            "\n[!] VFS_LOGIN / VFS_PASSWORD в .env не заданы (стоят заглушки).\n"
            "    Авто-вход не сработает — впишите реальные данные в .env.\n"
        )


async def _save_options(page: Page, settings) -> None:
    """Собрать варианты шага 1 и сохранить их в OPTIONS_FILE (JSON)."""
    print("\nСобираю доступные варианты (центры, категории, подкатегории)...")
    data = await _dump_options(page, settings)
    OPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    OPTIONS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total_sub = sum(len(v) for v in data["subcategories"].values())
    print(
        f"Сохранено в {OPTIONS_FILE}\n"
        f"   центров: {len(data['centers'])}, "
        f"категорий: {len(data['categories'])}, "
        f"подкатегорий всего: {total_sub}\n"
    )


async def run(
    url: str | None = None, steps_limit: int | None = None, dump: bool = False
) -> int:
    """Открыть логин, войти, проиграть сценарий и ждать закрытия окна.

    Args:
        url: Стартовый URL (по умолчанию страница логина).
        steps_limit: Сколько шагов выполнить (None — все).
        dump: Вместо выбора — собрать все варианты шага 1 в JSON-файл.
    """
    setup_logger()
    settings = get_settings()
    target_url = url or (settings.vfs_base_url.rstrip("/") + "/login")

    _warn_if_no_credentials()

    browser_manager = BrowserManager()
    await browser_manager.start(
        headless=False, persistent=True, user_data_dir=PROFILE_DIR
    )
    try:
        context = await browser_manager.new_context()
        page = context.pages[0] if context.pages else await context.new_page()
        logger.info("Открываю страницу: {}", target_url)
        await page.goto(target_url, wait_until="domcontentloaded")
        await _wait_if_cloudflare(page, browser_manager)
        await _warn_if_blocked(page)

        if dump:
            # Дойти до шага 1 (логин + «Записаться на прием»), не трогая списки.
            first_select = next(
                (i for i, s in enumerate(STEPS) if s.get("action") == "select"),
                len(STEPS),
            )
            page = await _run_steps(context, page, browser_manager, first_select)
            await _save_options(page, settings)
        else:
            page = await _run_steps(context, page, browser_manager, steps_limit)
            await _report_availability(page)

        print(f"\nОстановились на странице: {page.url}")
        print("Нажмите F12 → выберите элемент → правый клик → Copy → Copy selector.")
        print("Скопированный селектор пришлите мне — добавим следующий шаг.")
        print("Окно НЕ закроется само — закройте его вручную, когда закончите.\n")

        while browser_manager.is_connected:
            await asyncio.sleep(0.5)

        logger.info("Окно браузера закрыто пользователем")
        return 0
    finally:
        await browser_manager.stop()


def main() -> None:
    """Разобрать аргументы и запустить сценарий."""
    parser = argparse.ArgumentParser(
        description="Открыть VFS, войти и проиграть сценарий записи",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Стартовый URL (по умолчанию страница логина VFS)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=None,
        help="Сколько шагов выполнить: 0 — ни одного, N — первые N (по умолчанию все)",
    )
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Собрать все варианты центров/категорий/подкатегорий в data/vfs_options.json",
    )
    args = parser.parse_args()

    try:
        exit_code = asyncio.run(run(args.url, args.steps, dump=args.dump))
    except KeyboardInterrupt:
        exit_code = 0
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
