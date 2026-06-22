"""Роутеры-хендлеры команд бота.

Экспортирует список всех роутеров для регистрации в диспетчере.
"""

from bot.handlers import add, cancel, edit, start, status

# Порядок важен: команды /start и /help регистрируются первыми.
routers = [
    start.router,
    add.router,
    status.router,
    edit.router,
    cancel.router,
]

__all__ = ["routers"]
