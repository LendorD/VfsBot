"""VisaBooking — веб-сайт (FastAPI): отдаёт SPA и JSON-API.

Запуск из корня проекта:
    uvicorn webapp.main:app --reload
Открыть: http://127.0.0.1:8000

Фронтенд — статическая SPA (webapp/static/index.html + app.js), общается с
сервером через JSON-API (/api/*). Аутентификация — cookie-сессия. Заявки
хранятся в SQLite (webapp/data/webapp.db). Движок бронирования подключается
позже к /api/tasks/{id}/search.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from webapp import auth
from webapp.db import SessionLocal, Task, User, init_db

BASE_DIR = Path(__file__).resolve().parent            # backend/webapp
PROJECT_ROOT = BASE_DIR.parent                        # backend
OPTIONS_FILE = PROJECT_ROOT / "data" / "vfs_options.json"
# Фронтенд лежит отдельной папкой рядом с backend (../../frontend).
FRONTEND_DIR = BASE_DIR.parent.parent / "frontend"

app = FastAPI(title="VisaBooking")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("WEBAPP_SECRET", "dev-secret-change-me-in-production"),
)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.on_event("startup")
def _startup() -> None:
    init_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user(request: Request, db) -> User | None:
    user_id = request.session.get("user_id")
    return db.get(User, user_id) if user_id else None


def load_options() -> dict:
    if OPTIONS_FILE.exists():
        try:
            return json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"centers": [], "categories": [], "subcategories": {}}


def task_to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "site": t.site,
        "center": t.center,
        "category": t.category,
        "subcategory": t.subcategory,
        "date_start": t.date_start,
        "date_end": t.date_end,
        "applicants": t.applicants,
        "applicants_count": t.applicants_count,
        "auto_pay": t.auto_pay,
        "status": t.status,
    }


# ====================================================================== #
# SPA
# ====================================================================== #
@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ====================================================================== #
# API: аутентификация
# ====================================================================== #
@app.get("/api/me")
def api_me(request: Request, db=Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return {"email": user.email}


@app.post("/api/register")
async def api_register(request: Request, db=Depends(get_db)):
    body = await request.json()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or "@" not in email:
        return JSONResponse({"error": "Введите корректный email."}, status_code=400)
    if len(password) < 6:
        return JSONResponse({"error": "Пароль должен быть не короче 6 символов."}, status_code=400)
    if auth.get_user_by_email(db, email):
        return JSONResponse({"error": "Пользователь с таким email уже есть."}, status_code=400)
    user = auth.create_user(db, email, password)
    request.session["user_id"] = user.id
    return {"email": user.email}


@app.post("/api/login")
async def api_login(request: Request, db=Depends(get_db)):
    body = await request.json()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    user = auth.authenticate(db, email, password)
    if not user:
        return JSONResponse({"error": "Неверный email или пароль."}, status_code=401)
    request.session["user_id"] = user.id
    return {"email": user.email}


@app.post("/api/logout")
def api_logout(request: Request):
    request.session.clear()
    return {"ok": True}


# ====================================================================== #
# API: справочник вариантов
# ====================================================================== #
@app.get("/api/options")
def api_options():
    return load_options()


# ====================================================================== #
# API: заявки
# ====================================================================== #
@app.get("/api/tasks")
def api_tasks(request: Request, db=Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    tasks = sorted(user.tasks, key=lambda t: t.created_at, reverse=True)
    return [task_to_dict(t) for t in tasks]


@app.post("/api/tasks")
async def api_create_task(request: Request, db=Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = await request.json()
    applicants = body.get("applicants") or []
    task = Task(
        user_id=user.id,
        site=str(body.get("site", "vfs_fr")),
        center=str(body.get("center", "")),
        category=str(body.get("category", "")),
        subcategory=str(body.get("subcategory", "")),
        date_start=str(body.get("date_start", "")),
        date_end=str(body.get("date_end", "")),
        applicants_json=json.dumps(applicants, ensure_ascii=False),
        auto_pay=bool(body.get("auto_pay", False)),
        status="created",
    )
    db.add(task)
    db.commit()
    return task_to_dict(task)


@app.get("/api/tasks/{task_id}")
def api_task(task_id: int, request: Request, db=Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    task = db.get(Task, task_id)
    if not task or task.user_id != user.id:
        return JSONResponse({"error": "not found"}, status_code=404)
    return task_to_dict(task)


@app.delete("/api/tasks/{task_id}")
def api_delete_task(task_id: int, request: Request, db=Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    task = db.get(Task, task_id)
    if task and task.user_id == user.id:
        db.delete(task)
        db.commit()
    return {"ok": True}


@app.post("/api/tasks/{task_id}/search")
def api_run_search(task_id: int, request: Request, db=Depends(get_db)):
    """Запустить поиск слотов (пока заглушка: ставит статус «searching»).

    TODO: подключить движок бронирования (vfs_site.booking_flow.BookingFlow):
    запустить браузер, пройти логин/критерии, читать доступность, при
    подходящей дате — бронировать (с учётом auto_pay).
    """
    user = current_user(request, db)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    task = db.get(Task, task_id)
    if not task or task.user_id != user.id:
        return JSONResponse({"error": "not found"}, status_code=404)
    task.status = "searching"
    db.commit()
    return task_to_dict(task)
