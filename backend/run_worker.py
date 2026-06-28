"""Запуск Python-воркера с правильным event loop (особенно для Windows).

Playwright запускает браузер через подпроцесс, а на Windows это работает только
на ProactorEventLoop. uvicorn с --reload использует SelectorEventLoop в дочернем
процессе и падает с NotImplementedError. Здесь мы ставим политику ДО старта
uvicorn и запускаем БЕЗ reload — браузер стабильно стартует.

Запуск (из backend/):
    python run_worker.py
"""

from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("worker_app:app", host="127.0.0.1", port=8800, reload=False)
