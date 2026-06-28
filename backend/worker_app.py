"""Python-воркер: HTTP-обёртка над движком обхода VFS.

Это сервис, который вызывает Go-бэкенд. Go кладёт задание (войти, выбрать
критерии, проверить/забронировать слот), воркер исполняет его в браузере
(Playwright/patchright) и возвращает результат.

Задания асинхронные (браузер — долго): POST /jobs создаёт задание и сразу
возвращает job_id, а GET /jobs/{id} отдаёт статус и результат.

Запуск (из backend/):
    uvicorn worker_app:app --host 0.0.0.0 --port 8800

Состояние реализации:
    • вход + выбор критериев + чтение доступности — РАБОТАЕТ;
    • бронирование (форма/календарь/оплата) — ждёт селекторов (booking_flow).
"""

from __future__ import annotations

import asyncio
import sys
import uuid

# На Windows запуск браузера идёт через подпроцесс, а он работает только на
# ProactorEventLoop. uvicorn --reload иначе использует SelectorEventLoop и
# падает с NotImplementedError. Ставим политику до создания event loop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, Field

from vfs_site import availability
from vfs_site.booking_flow import BookingFlow
from vfs_site.browser import BrowserManager
from core.booking_task import BookingCriteria
from core.config import get_settings
from core.logger import setup_logger

setup_logger()
app = FastAPI(title="VFS Worker")

PROFILE_DIR = str(Path(__file__).resolve().parent / ".browser_profile")

# Простое in-memory хранилище заданий (для одного процесса-воркера).
JOBS: dict[str, dict] = {}


class CheckRequest(BaseModel):
    """Входные данные задания проверки доступности."""

    login: str
    password: str
    center: str
    category: str
    subcategory: str
    date_start: str | None = Field(default=None, description="YYYY-MM-DD")
    date_end: str | None = Field(default=None, description="YYYY-MM-DD")
    applicants_count: int = Field(default=1, ge=1)


def _parse(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return date.fromisoformat(d)
    except ValueError:
        return None


class BrowserSlot:
    """Один браузер пула: своя сессия и профиль, одна задача за раз.

    Браузер открывается лениво и НЕ закрывается между заданиями — вход и
    пройденный Cloudflare сохраняются. У каждого слота свой каталог профиля
    (Chromium блокирует профиль, поэтому делить один нельзя).
    """

    def __init__(self, index: int) -> None:
        self.index = index
        # Слот 0 использует уже «прогретый» профиль, остальные — отдельные.
        self.profile = PROFILE_DIR if index == 0 else f"{PROFILE_DIR}_{index}"
        self.manager: BrowserManager | None = None
        self.page = None

    async def get_page(self):
        settings = get_settings()
        if (
            self.manager is None
            or not self.manager.is_connected
            or self.page is None
            or self.page.is_closed()
        ):
            self.manager = BrowserManager()
            await self.manager.start(
                headless=settings.browser_headless,
                persistent=True,
                user_data_dir=self.profile,
            )
            context = await self.manager.new_context()
            self.page = context.pages[0] if context.pages else await context.new_page()
            logger.info("Браузер #{} открыт (профиль {})", self.index, self.profile)
        return self.page

    async def close(self) -> None:
        if self.manager is not None:
            await self.manager.stop()


# Пул браузеров: задание берёт свободный браузер и возвращает его (не закрывая).
# Размер пула = worker_browsers. Несколько браузеров → параллельные задачи.
_pool: asyncio.Queue | None = None


@app.on_event("startup")
async def _startup() -> None:
    global _pool
    _pool = asyncio.Queue()
    count = max(1, get_settings().worker_browsers)
    for i in range(count):
        await _pool.put(BrowserSlot(i))
    logger.info("Пул браузеров инициализирован: {} шт.", count)


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _pool is None:
        return
    while not _pool.empty():
        slot = await _pool.get()
        await slot.close()


async def _run_check(job_id: str, req: CheckRequest) -> None:
    """Фоновое выполнение задания: берёт свободный браузер из пула,
    выполняет вход → критерии → чтение доступности и возвращает браузер в пул.
    """
    job = JOBS[job_id]
    job["status"] = "running"
    slot = await _pool.get()  # ждёт свободный браузер из пула
    try:
        page = await slot.get_page()

        flow = BookingFlow(page)
        await flow.login_and_open(req.login, req.password)

        start, end = _parse(req.date_start), _parse(req.date_end)
        task_like = SimpleNamespace(
            criteria=BookingCriteria(
                center=req.center, category=req.category, subcategory=req.subcategory
            ),
            applicants_count=req.applicants_count,
            date_start=start,
            date_end=end,
        )
        await flow.select_criteria(task_like)

        avail = await availability.read_availability(page)
        matched = availability.matches_desired(
            avail, applicants=req.applicants_count, start=start, end=end
        )
        job["result"] = {
            "has_slots": avail.has_slots,
            "nearest": {str(k): v.isoformat() for k, v in avail.nearest.items()},
            "matched": matched.isoformat() if matched else None,
        }
        job["status"] = "done"
        logger.info("Задание {} (браузер #{}) завершено: {}", job_id, slot.index, job["result"])
    except Exception as exc:  # noqa: BLE001
        job["status"] = "error"
        job["message"] = str(exc)
        logger.warning("Задание {} ошибка: {}", job_id, exc)
    finally:
        await _pool.put(slot)  # вернуть браузер в пул (не закрываем)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/jobs")
async def create_job(req: CheckRequest, background: BackgroundTasks) -> dict:
    """Создать задание проверки доступности. Возвращает job_id."""
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status": "pending", "result": None, "message": None}
    background.add_task(_run_check, job_id, req)
    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Статус и результат задания."""
    job = JOBS.get(job_id)
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"job_id": job_id, **job}
